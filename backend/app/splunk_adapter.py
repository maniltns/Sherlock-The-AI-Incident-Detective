# backend/app/splunk_adapter.py
"""
Splunk adapter: attempt to run a oneshot export search via Splunk REST API.
If SPLUNK_BASE_URL and SPLUNK_TOKEN are not configured, return a simulated
result by scanning the local sample_logs.jsonl for matching lines.

Environment variables used:
 - SPLUNK_BASE_URL e.g. https://splunk.example.com:8089
 - SPLUNK_TOKEN (Bearer token for Authorization header)
 - SPLUNK_DEFAULT_INDEX (optional) index to search by default
"""
import os
import json
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("splunk_adapter")
logger.setLevel(logging.INFO)

SPLUNK_BASE_URL = os.getenv("SPLUNK_BASE_URL")
SPLUNK_TOKEN = os.getenv("SPLUNK_TOKEN")
SPLUNK_DEFAULT_INDEX = os.getenv("SPLUNK_DEFAULT_INDEX", "")

# internal fallback to local sample logs
from .collectors import _load_logs  # local helper in collectors.py

def _simulate_splunk(query: str, minutes: int = 30, max_results: int = 50) -> List[Dict]:
    """
    Fallback when Splunk is not available: use sample_logs.jsonl and return
    items that match query tokens (recent first).
    """
    logger.info("Splunk not configured: using local sample log simulation")
    out = []
    q = (query or "").lower()
    tokens = set(q.split())
    all_logs = _load_logs()
    for rec in reversed(all_logs):
        msg = rec.get("message", "").lower()
        host = rec.get("host", "").lower()
        if not query:
            out.append(rec)
        elif q in msg or q in host or (tokens and (tokens & set(msg.split()))):
            out.append(rec)
        if len(out) >= max_results:
            break
    # convert to Splunk-like structure
    results = []
    for i, r in enumerate(out, start=1):
        results.append({
            "raw": r.get("message", ""),
            "_time": r.get("timestamp"),
            "host": r.get("host"),
            "level": r.get("level"),
            "index": "simulated"
        })
    return results

def splunk_search(query: str, minutes: int = 30, max_results: int = 50, timeout: int = 8) -> List[Dict]:
    """
    Query Splunk using the export oneshot endpoint.
    Returns list of dicts: each with keys raw, _time, host, level, index...
    If Splunk not configured or call fails, falls back to _simulate_splunk.
    """
    if not SPLUNK_BASE_URL or not SPLUNK_TOKEN:
        return _simulate_splunk(query, minutes, max_results)

    # Build a Splunk search string (oneshot) - safe minimal search
    # NOTE: users should customize the index as needed via SPLUNK_DEFAULT_INDEX
    q_index = f"index={SPLUNK_DEFAULT_INDEX}" if SPLUNK_DEFAULT_INDEX else ""
    # Escape query minimally: we assume incoming query is a natural language string - include it as terms
    search_terms = query.strip()
    if search_terms:
        # use simple search concatenation
        search_str = f"search {q_index} {search_terms}"
    else:
        search_str = f"search {q_index} | head {max_results}"

    # REST endpoint: /services/search/jobs/export for oneshot
    export_endpoint = SPLUNK_BASE_URL.rstrip("/") + "/services/search/jobs/export"
    headers = {
        "Authorization": f"Bearer {SPLUNK_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "search": search_str,
        "output_mode": "json",
        "count": str(max_results),
        # optionally set earliest_time to relative minutes
        "earliest_time": f"-{minutes}m"
    }

    try:
        import requests
        logger.info("Calling Splunk export: %s", export_endpoint)
        resp = requests.post(export_endpoint, headers=headers, data=payload, timeout=timeout, verify=True)
        if resp.status_code != 200:
            logger.error("Splunk returned status %s: %s", resp.status_code, resp.text[:200])
            return _simulate_splunk(query, minutes, max_results)
        # Splunk export returns newline-delimited JSON events in many setups; try to parse robustly
        lines = [ln for ln in resp.text.splitlines() if ln.strip()]
        results = []
        for ln in lines:
            try:
                j = json.loads(ln)
                # Splunk "result" format may put event under "result" or "data"
                evt = j.get("result") or j.get("event") or j.get("data") or j
                # normalize
                raw = evt.get("_raw") or evt.get("raw") or evt.get("message") or str(evt)
                _time = evt.get("_time") or evt.get("time") or None
                host = evt.get("host") or evt.get("source") or evt.get("hostname")
                level = (evt.get("level") or "").upper() if isinstance(evt.get("level"), str) else evt.get("level")
                results.append({"raw": raw, "_time": _time, "host": host, "level": level, "index": evt.get("index")})
                if len(results) >= max_results:
                    break
            except Exception:
                # if a line isn't JSON (rare), keep the line as raw
                results.append({"raw": ln, "_time": None, "host": None, "level": None, "index": "unknown"})
                if len(results) >= max_results:
                    break
        return results
    except Exception as e:
        logger.exception("Splunk call failed: %s", e)
        return _simulate_splunk(query, minutes, max_results)
