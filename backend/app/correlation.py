from typing import List, Dict, Tuple
import datetime
from collections import Counter


def correlate_evidence(
    evidence_items: List[Dict],
    query: str,
    return_summary: bool = False
) -> List[Dict] or Tuple[List[Dict], Dict]:
    """
    Enterprise-grade evidence scorer.

    Scoring rules:
    - Type weights: metric(40), splunk_log(30), log(20), git(10)
    - Severity keywords bump: +30
    - Token overlap with query: +25
    - Numeric signal bump (HTTP codes, counts): +5
    - Recency (<60m): +20
    - Additional type heuristics (metrics, splunk)
    """

    q_tokens = set((query or "").lower().split())
    now = datetime.datetime.utcnow()
    scored = []

    type_weight = {
        "metric": 40,
        "splunk_log": 30,
        "log": 20,
        "git": 10,
        None: 5,
    }

    severity_keywords = [
        "error", "exception", "timeout", "oom", "outofmemory",
        "exhausted", "critical", "fatal", "panic"
    ]

    # summary aggregators
    host_counter = Counter()
    type_counter = Counter()
    severity_counter = Counter()

    for ev in evidence_items:
        base = type_weight.get(ev.get("type"), type_weight[None])
        score = base

        text = (ev.get("text") or "").lower()
        ts = ev.get("timestamp")

        # severity bump
        if any(k in text for k in severity_keywords):
            score += 30
            severity_counter["error_like"] += 1

        # token overlap bump
        if q_tokens and (q_tokens & set(text.split())):
            score += 25

        # numeric bump
        if any(tok.isdigit() and len(tok) <= 4 for tok in text.split()):
            score += 5

        # recency bump (60 min)
        try:
            if ts:
                try:
                    t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except:
                    t = datetime.datetime.fromisoformat(ts)

                delta = (
                    now.replace(tzinfo=None)
                    - (t.replace(tzinfo=None) if t.tzinfo else t)
                ).total_seconds()

                if abs(delta) <= 3600:
                    score += 20

        except Exception:
            pass

        # type-specific
        ev_type = ev.get("type")

        if ev_type == "metric":
            # metric signals often include warning numbers
            if "%" in text or any(
                int(tok) >= 80 for tok in text.split() if tok.isdigit()
            ):
                score += 10

        if ev_type == "splunk_log":
            # long stack traces get slight bump
            if len(text) > 200:
                score += 8

        # clamp
        score = min(score, 100)

        ev2 = dict(ev)
        ev2["score"] = int(score)
        scored.append(ev2)

        # summary
        host_counter[ev.get("host") or "unknown"] += 1
        type_counter[ev_type or "unknown"] += 1

    # sort by score, then recency
    def _sort_key(x):
        ts = x.get("timestamp")
        try:
            t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.datetime.fromtimestamp(0)
        except:
            t = datetime.datetime.fromtimestamp(0)
        return (x.get("score", 0), t)

    scored.sort(key=_sort_key, reverse=True)

    # summary block
    summary = {
        "total_evidence": len(evidence_items),
        "by_type": dict(type_counter),
        "by_host": dict(host_counter.most_common(10)),
        "severity_counts": dict(severity_counter),
        "top_scores_sample": [
            {"id": x.get("id"), "type": x.get("type"), "score": x.get("score")}
            for x in scored[:6]
        ]
    }

    return (scored, summary) if return_summary else scored
