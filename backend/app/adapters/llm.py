"""Anthropic Claude wrapper (Section 1.4 model allocation).

Models are used only for classification, extraction and narrative generation —
never for arithmetic, never to recall or generate reference facts. All calls
run at temperature 0 so two runs on the same input produce identical output
(Section 11.4 reproducibility). When no API key is configured, `enabled` is
False and callers fall back to deterministic behaviour.
"""
from __future__ import annotations

import json

from app.config import Settings
from app.data.records import TitleClass


class LLM:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        if settings.llm_enabled:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            except Exception:
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _complete(self, model: str, system: str, user: str, max_tokens: int) -> str:
        msg = self._client.messages.create(
            model=model, max_tokens=max_tokens,
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

    # --- small model: sector classification for the reference lookup ---
    def classify_sector(self, text: str, sector_keys: list[str]) -> str:
        if not self.enabled:
            return ""
        system = (
            "You map a company to exactly one sector key from a fixed list, using "
            "its website text. Reply with the single key only, nothing else."
        )
        user = f"Keys: {', '.join(sector_keys)}\n\nWebsite text:\n{text}"
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
