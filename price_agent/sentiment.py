"""Label review text as good, bad or neutral with VADER, a free rule-based sentiment model."""

from __future__ import annotations

from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

GOOD_FROM = 0.05  # VADER's recommended cut-offs for its compound score
BAD_TO = -0.05


@lru_cache(maxsize=1)
def _analyzer() -> SentimentIntensityAnalyzer:
    return SentimentIntensityAnalyzer()


def label(text: str) -> str:
    compound = _analyzer().polarity_scores(text)["compound"]
    if compound >= GOOD_FROM:
        return "good"
    if compound <= BAD_TO:
        return "bad"
    return "neutral"


def summarize(texts: list[str]) -> dict[str, int]:
    counts = {"good": 0, "bad": 0, "neutral": 0}
    for text in texts:
        counts[label(text)] += 1
    return counts
