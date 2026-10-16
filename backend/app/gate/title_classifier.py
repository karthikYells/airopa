"""Job-title classifier (Section 3.3).

Dictionary match FIRST (zero model cost); a model is called only for titles the
dictionary cannot resolve, and only when an LLM is configured. When no model is
available an unresolved title is classed AMBIGUOUS, which is the safe bias: it
never counts toward disqualification and it feeds the >40% ambiguous CAUTION
valve, so borderline companies reach a human rather than being silently dropped.

Two runs on the same input data must produce the same classification, so the
dictionary path is fully deterministic and model results are cached per title
(see adapters/llm.py). With a model configured, titles the dictionary leaves
unresolved or AMBIGUOUS are sent to it in a single batch.
"""
from __future__ import annotations

import re
import unicodedata

from app.data.records import ClassifiedTitle, TitleClass
from app.gate import title_dictionary as D

_PUNCT = re.compile(r"[^a-z0-9&/ ]+")
_WS = re.compile(r"\s+")


def normalise(raw: str) -> str:
    """Lowercase, strip accents/punctuation, translate, strip seniority,
    collapse whitespace. The qualifying noun is preserved."""
    s = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()

    # Translate whole-phrase first, then token-wise (Section 3.3 translation map).
    if s in D.TRANSLATIONS:
        s = D.TRANSLATIONS[s]
    else:
        toks = [D.TRANSLATIONS.get(t, t) for t in s.split()]
        s = " ".join(toks)

    # Strip seniority / grade tokens (but never let the string become empty).
    tokens = [t for t in s.split() if t not in D.SENIORITY_TOKENS]
    if tokens:
        s = " ".join(tokens)
    return _WS.sub(" ", s).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Whole-token containment so 'developer' does not match 'developerx'."""
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _dictionary_match(norm: str) -> tuple[TitleClass, str, float] | None:
    """Priority: IT_SUPPORT -> NON_TECH -> TECH -> contextual/ambiguous.

    NON_TECH is checked before TECH so plant/process engineering titles
    ('manufacturing engineer', 'quality engineer') are not swept up by a
    generic tech term. Returns (class, method, confidence) or None.
    """
    for phrase in D.IT_SUPPORT_TITLES:
        if _contains_phrase(norm, phrase):
            return TitleClass.IT_SUPPORT, "dictionary", 0.95

    for phrases in D.NON_TECH_TITLES.values():
        for phrase in phrases:
            if _contains_phrase(norm, phrase):
                return TitleClass.NON_TECH, "dictionary", 0.9

    for phrases in D.TECH_TITLES.values():
        for phrase in phrases:
            if _contains_phrase(norm, phrase):
                return TitleClass.TECH, "dictionary", 0.9

    # Contextual tech titles need a cue we do not reliably have here -> ambiguous.
    for phrases in D.TECH_CONTEXTUAL.values():
        for phrase in phrases:
            if _contains_phrase(norm, phrase):
                return TitleClass.AMBIGUOUS, "dictionary", 0.5

    # Explicit ambiguous tokens (default NON-TECH when counting, but tracked).
    for phrase in D.AMBIGUOUS_TITLES:
        if _contains_phrase(norm, phrase):
            return TitleClass.AMBIGUOUS, "dictionary", 0.5

    return None


def classify_one(raw: str, llm=None, context: str | None = None) -> ClassifiedTitle:
    norm = normalise(raw)
    hit = _dictionary_match(norm)
    if hit is not None:
        cls, method, conf = hit
        return ClassifiedTitle(raw=raw, normalised=norm, title_class=cls,
                               method=method, confidence=conf)

    # Dictionary miss. Try the model only if one is configured.
    if llm is not None and llm.enabled:
        cls, conf = llm.classify_title(norm, context=context)
        return ClassifiedTitle(raw=raw, normalised=norm, title_class=cls,
                               method="model", confidence=conf)

    # No model: safe bias — AMBIGUOUS (never counts as tech, feeds CAUTION valve).
    return ClassifiedTitle(raw=raw, normalised=norm,
                           title_class=TitleClass.AMBIGUOUS,
                           method="default", confidence=0.3)


def classify_titles(
    raw_titles: list[str], llm=None, context: str | None = None
) -> list[ClassifiedTitle]:
    """Dictionary first; every title it leaves unresolved or AMBIGUOUS goes to
    the model in one batch (when configured). Without a model this is exactly
    the per-title dictionary path."""
    if llm is None or not llm.enabled or not hasattr(llm, "classify_titles_batch"):
        return [classify_one(t, llm=llm, context=context) for t in raw_titles]

    out: list[ClassifiedTitle | None] = []
    pending: list[tuple[int, str, str]] = []  # (index, raw, normalised)
    for raw in raw_titles:
        norm = normalise(raw)
        hit = _dictionary_match(norm)
        if hit is not None and hit[0] is not TitleClass.AMBIGUOUS:
            cls, method, conf = hit
            out.append(ClassifiedTitle(raw=raw, normalised=norm, title_class=cls,
                                       method=method, confidence=conf))
        else:
            pending.append((len(out), raw, norm))
            out.append(None)

    if pending:
        labels = llm.classify_titles_batch([raw for _, raw, _ in pending], context=context)
        for i, raw, norm in pending:
            cls, conf = labels[raw]
            out[i] = ClassifiedTitle(raw=raw, normalised=norm, title_class=cls,
                                     method="model", confidence=conf)
    return out  # type: ignore[return-value]


def title_mix(classified: list[ClassifiedTitle]) -> dict:
    """Counts and shares by class, retained for audit (Section 3.3)."""
    total = len(classified) or 1
    counts = {c: 0 for c in TitleClass}
    for ct in classified:
        counts[ct.title_class] += 1
    return {
        "total": len(classified),
        "counts": {c.value: counts[c] for c in TitleClass},
        "shares": {c.value: round(counts[c] / total, 4) for c in TitleClass},
    }
