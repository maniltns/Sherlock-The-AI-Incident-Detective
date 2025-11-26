# backend/app/collectors.py
import os
import json
import random
import datetime
from typing import List, Dict

DATA_DIR = os.path.join(os.getcwd(), "model_data")
LOG_FILE = os.path.join(DATA_DIR, "sample_logs.jsonl")
DEPLOYS_FILE = os.path.join(DATA_DIR, "deploys.json")

# ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)
# create files if not exist
for f in (LOG_FILE, DEPLOYS_FILE):
    if not os.path.exists(f):
        with open(f, "w") as fh:
            if f == DEPLOYS_FILE:
                fh.write("[]\n")

def _now_iso(offset_seconds=0):
    return (datetime.datetime.utcnow() - datetime.timedelta(seconds=offset_seconds)).isoformat() + "Z"

def generate_sample_incident(scenario="pool", count=10) -> List[Dict]:
    """
    Append 'count' fabricated log entries and optionally a deploy stub.
    scenarios: 'pool' | 'oom' | 'external' | 'network' | 'cpu' | 'memory' | 'api'
    Returns list of created log dicts.
    """
    logs = []
    hosts = ["api-prod-01", "api-prod-02", "db-prod-01", "web-prod-01"]
    commit_msgs = {
        "pool": "Commit abc123: increased connection pool default to 50 in db client config",
        "oom": "Commit def456: adjusted JVM heap memory settings to 1024MB",
        "external": "Commit ghi789: updated third-party API client timeout to 60s",
        "network": "Commit jkl012: modified network config for increased bandwidth limits",
        "cpu": "Commit mno345: optimized CPU-intensive threads with concurrency limits",
        "memory": "Commit pqr678: implemented garbage collection optimizations",
        "api": "Commit stu901: added API rate limiting middleware",
    }
    for i in range(count):
        ts = _now_iso(offset_seconds=random.randint(0, 1800))
        host = random.choice(hosts)
        if scenario == "pool":
            msg = f"{ts} ERROR [{host}] Connection pool exhausted: max_size=50 used=50"
        elif scenario == "oom":
            msg = f"{ts} ERROR [{host}] OutOfMemoryError: Java heap space; process killed"
        elif scenario == "external":
            msg = f"{ts} WARN [{host}] third-party-api timeout: upstream latency 1200ms"
        elif scenario == "network":
            msg = f"{ts} ERROR [{host}] Connection refused: No route to host xxx.xxx.xxx.xxx"
        elif scenario == "cpu":
            msg = f"{ts} WARN [{host}] High CPU usage: 95% sustained, potential deadlock"
        elif scenario == "memory":
            msg = f"{ts} ERROR [{host}] Memory leak detected: Resident set size exceeded 8GB limit"
        elif scenario == "api":
            msg = f"{ts} ERROR [{host}] API rate limit exceeded: Too many requests (429)"
        else:
            msg = f"{ts} INFO [{host}] synthetic log line {i}"
        log_entry = {"timestamp": ts, "host": host, "level": "ERROR" if "ERROR" in msg else "WARN" if "WARN" in msg else "INFO", "message": msg}
        logs.append(log_entry)
        with open(LOG_FILE, "a") as fh:
            fh.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # append a deploy stub for context
    deploy = {
        "timestamp": _now_iso(offset_seconds=900),
        "commit": "dummycommit",
        "message": commit_msgs.get(scenario, "Commit dummy: general fix")
    }
    try:
        with open(DEPLOYS_FILE, "r+") as fh:
            arr = json.load(fh)
            arr.append(deploy)
            fh.seek(0)
            json.dump(arr, fh, ensure_ascii=False, indent=2)
            fh.truncate()
    except Exception:
        # fallback: overwrite cleanly
        with open(DEPLOYS_FILE, "w") as fh:
            json.dump([deploy], fh, ensure_ascii=False, indent=2)

    return logs

def _load_logs() -> List[Dict]:
    if not os.path.exists(LOG_FILE):
        return []
    out = []
    with open(LOG_FILE, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # tolerant parse: try to salvage message lines
                out.append({"timestamp": None, "host": "unknown", "level": "INFO", "message": line})
    return out

def search_logs(query: str, minutes: int = 30) -> List[Dict]:
    """
    Simple substring-based search over sample_logs.jsonl.
    Returns most recent matches first (no heavy indexing needed).
    """
    all_logs = _load_logs()
    if not query:
        return all_logs[-50:][::-1]  # last 50 logs
    q = query.lower()
    matches = []
    # naive token match
    for rec in reversed(all_logs):  # recent first
        msg = rec.get("message", "").lower()
        host = rec.get("host", "").lower()
        if q in msg or q in host:
            matches.append(rec)
        # also include if any token intersects
        else:
            q_tokens = set(q.split())
            msg_tokens = set(msg.split())
            if q_tokens & msg_tokens:
                matches.append(rec)
        if len(matches) >= 50:
            break
    return matches

def fetch_deploys_stub(query: str, minutes: int = 30) -> List[Dict]:
    """
    Load deploy stubs from deploys.json for correlation, filtered by query.
    """
    try:
        with open(DEPLOYS_FILE, "r") as fh:
            arr = json.load(fh)
            if not query:
                return arr[-10:]
            q = query.lower()
            matches = []
            for d in arr:
                msg = d.get("message", "").lower()
                if q in msg or any(token in msg for token in q.split()):
                    matches.append(d)
            return matches[-10:]
    except Exception:
        return []
