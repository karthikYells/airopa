"""Anthropic Claude wrapper (Section 1.4 model allocation).

Models are used only for classification, extraction and narrative generation —
never for arithmetic, never to recall or generate reference facts. Current
models do not accept a temperature setting, so title classes are cached per
instance to keep a run self-consistent (Section 11.4 reproducibility). When no
API key is configured, `enabled` is False and callers fall back to
deterministic behaviour.
"""
from __future__ import annotations

import json

from app.config import Settings
from app.data.records import TitleClass


class LLM:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        self._title_cache: dict[str, tuple[TitleClass, float]] = {}
        if settings.llm_enabled:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            except Exception:
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    # Current models think before answering and that counts against max_tokens;
    # without headroom a short answer (a 20-token sector key) comes back empty.
    _THINKING_HEADROOM = 2048

    def _complete(self, model: str, system: str, user: str, max_tokens: int) -> str:
        """`max_tokens` is the answer budget; thinking headroom is added on top."""
        msg = self._client.messages.create(
            model=model, max_tokens=max_tokens + self._THINKING_HEADROOM,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    # --- small/cheap model: classification only (Section 3.3 fallback) ---
    def classify_title(self, normalised: str, context: str | None = None) -> tuple[TitleClass, float]:
        if not self.enabled:
            return TitleClass.AMBIGUOUS, 0.3
        system = (
            "You classify a single job title into exactly one label for an India "
            "capability-centre screen. Labels: TECH (software/platform/data/security/"
            "product engineering), NON_TECH (commercial, finance, plant/process "
            "engineering, field service, country leadership), IT_SUPPORT (helpdesk/"
            "desktop/site IT), AMBIGUOUS (cannot tell without more context). "
            "Plant, manufacturing, process and field engineering are NON_TECH. "
            'Reply with JSON only: {"label": "...", "confidence": 0.0}.'
        )
        user = f"Title: {normalised}\nContext: {context or 'none'}"
        try:
            raw = self._complete(self._settings.llm_model_small, system, user, 100)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            label = TitleClass(data["label"])
            return label, float(data.get("confidence", 0.6))
        except Exception:
            return TitleClass.AMBIGUOUS, 0.3

    def classify_titles_batch(self, titles: list[str], context: str | None = None
                              ) -> dict[str, tuple[TitleClass, float]]:
        """Classify many titles in one call per chunk (a people search returns
        ~100). Results are cached on the instance so a title is classed once per
        run. Titles the model fails on come back AMBIGUOUS."""
        out: dict[str, tuple[TitleClass, float]] = {}
        todo = [t for t in dict.fromkeys(titles) if t not in self._title_cache]
        if self.enabled:
            system = (
                "You classify job titles for an India capability-centre screen. "
                "Labels: TECH (software/platform/data/security/product engineering, "
                "enterprise applications such as SAP), NON_TECH (commercial, finance, "
                "HR, plant/process/mechanical/design engineering, field service, "
                "country leadership), IT_SUPPORT (helpdesk/desktop/site IT), "
                "AMBIGUOUS (cannot tell without more context). Plant, manufacturing, "
                "process, mechanical, CAD and field engineering are NON_TECH. "
                'Reply with JSON only: {"<title>": {"label": "...", "confidence": 0.0}, ...} '
                "using each title exactly as given."
            )
            for i in range(0, len(todo), 50):
                chunk = todo[i:i + 50]
                user = f"Context: {context or 'none'}\nTitles:\n" + "\n".join(chunk)
                try:
                    raw = self._complete(self._settings.llm_model_small, system, user, 4000)
                    data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
                except Exception:
                    data = {}
                for t in chunk:
                    try:
                        item = data[t]
                        self._title_cache[t] = (TitleClass(item["label"]),
                                                float(item.get("confidence", 0.6)))
                    except Exception:
                        self._title_cache[t] = (TitleClass.AMBIGUOUS, 0.3)
        for t in titles:
            out[t] = self._title_cache.get(t, (TitleClass.AMBIGUOUS, 0.3))
        return out

    # --- small model: sector classification for the reference lookup ---
    def classify_sector(self, text: str, sector_keys: list[str], name: str | None = None,
                        industry: str | None = None) -> str:
        if not self.enabled:
            return ""
        system = (
            "You map a company to exactly one sector key from a fixed list. Classify "
            "by what the company itself makes or does, not by who its customers are: "
            "a maker of packaging machines for bakeries is industrial_machinery, not "
            "food_beverage; an online supermarket with its own delivery is "
            "logistics_distribution or consumer_goods, not software_saas; a wholesale "
            "distributor of parts is logistics_distribution. Ignore cookie banners, "
            "navigation and language pickers. Reply with the single key only."
        )
        user = (f"Keys: {', '.join(sector_keys)}\n\nCompany: {name or 'unknown'}\n"
                f"Registry industry: {industry or 'unknown'}\n\nWebsite text:\n{text}")
        try:
            out = self._complete(self._settings.llm_model_small, system, user, 20)
            return out.strip().split()[0].strip(".,")
        except Exception:
            return ""

    # --- strong model: Tier-3 narrative from resolved facts only (Section 10.1) ---
    def generate_narrative(self, system: str, facts_json: str) -> str:
        if not self.enabled:
            return ""
        try:
            return self._complete(self._settings.llm_model_large, system,
                                  facts_json, 1200).strip()
        except Exception:
            return ""
