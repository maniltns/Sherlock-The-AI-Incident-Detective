# backend/app/correlation.py
from typing import List, Dict
import datetime

def _contains_keywords(text: str, tokens: set) -> bool:
    t = text.lower()
    return any(tok in t for tok in tokens)

def correlate_evidence(evidence_items: List[Dict], query: str) -> List[Dict]:
    """
    Score evidence items with a simple tunable heuristic.
    Returns list sorted descending by score. Each item augmented with 'score'.
    """
    q_tokens = set(query.lower().split())
    scored = []
    for ev in evidence_items:
        score = 10
        text = ev.get("text", "").lower()
        # severity
        if any(k in text for k in ["error", "exception", "timeout", "oom", "outofmemory", "exhausted"]):
            score += 30
        # keyword overlap
        if q_tokens & set(text.split()):
            score += 30
        # time-based bump (if timestamp present and within few minutes of now)
        ts = ev.get("timestamp")
        if ts:
            try:
                # parse rough ISO
                then = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                now = datetime.datetime.utcnow()
                delta = now - then
                if abs(delta.total_seconds()) <= 3600:  # within last 60m
                    score += 20
            except Exception:
                pass
        # type bump
        if ev.get("type") == "git":
            score += 10

        # clamp
        if score > 100:
            score = 100
        ev2 = dict(ev)
        ev2["score"] = score
        scored.append(ev2)
    # sort
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
