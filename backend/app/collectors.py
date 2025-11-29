# backend/app/collectors.py
import os
import json
import random
import datetime
from typing import List, Dict, Optional

# Data directory inside container (volume mounted)
DATA_DIR = os.path.join(os.getcwd(), "model_data")
LOG_FILE = os.path.join(DATA_DIR, "sample_logs.jsonl")
DEPLOYS_FILE = os.path.join(DATA_DIR, "deploys.json")
METRICS_FILE = os.path.join(DATA_DIR, "zabbix_metrics.jsonl")

os.makedirs(DATA_DIR, exist_ok=True)
# ensure files exist
for f, init in ((LOG_FILE, None), (DEPLOYS_FILE, "[]\n"), (METRICS_FILE, None)):
    if not os.path.exists(f):
        with open(f, "w") as fh:
            if init:
                fh.write(init)

def _utc_now():
    # timezone-aware UTC
    return datetime.datetime.now(datetime.timezone.utc)

def _now_iso(offset_seconds: int = 0):
    return ( _utc_now() - datetime.timedelta(seconds=offset_seconds) ).isoformat().replace("+00:00", "Z")

def _parse_iso(ts: Optional[str]):
    if not ts:
        return None
    # convert string like 2025-11-26T12:54:00.235026Z to aware datetime
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        # try safe fallback
        try:
            return datetime.datetime.fromisoformat(ts + "+00:00")
        except Exception:
            return None

#
# Synthetic generation
#
def generate_sample_incident(scenario: str = "pool", count: int = 10) -> List[Dict]:
    """
    Create synthetic logs, a deploy stub and zabbix metrics for demo.
    scenarios include: pool, oom, external, network, cpu, memory, api
    """
    logs = []
    hosts = ["api-prod-01", "api-prod-02", "db-prod-01", "web-prod-01"]
    commit_msgs = {
        "pool": "Commit abc123: changed DB client pool default to 50 (increase concurrency)",
        "oom": "Commit def456: changed JVM heap settings to 1024MB",
        "external": "Commit ghi789: updated thirdparty API timeout to 60s",
        "network": "Commit jkl012: changed VPC route policy",
        "cpu": "Commit mno345: introduced threadpool changes",
        "memory": "Commit pqr678: adjusted GC flags",
        "api": "Commit stu901: added rate limiter middleware",
    }

    # create logs
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
            msg = f"{ts} ERROR [{host}] Connection refused: No route to host 10.20.30.40"
        elif scenario == "cpu":
            msg = f"{ts} WARN [{host}] High CPU usage: 95% sustained, potential deadlock"
        elif scenario == "memory":
            msg = f"{ts} ERROR [{host}] Memory leak detected: RSS > 8GB"
        elif scenario == "api":
            msg = f"{ts} ERROR [{host}] API rate limit exceeded: Too many requests (429)"
        else:
            msg = f"{ts} INFO [{host}] synthetic log line {i}"
        log_entry = {
            "timestamp": ts,
            "host": host,
            "level": "ERROR" if "ERROR" in msg else "WARN" if "WARN" in msg else "INFO",
            "message": msg
        }
        logs.append(log_entry)
        with open(LOG_FILE, "a") as fh:
            fh.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # deploy stub
    deploy = {
        "timestamp": _now_iso(offset_seconds=900),
        "commit": f"deploy-{random.randint(1000,9999)}",
        "message": commit_msgs.get(scenario, "Commit dummy: general fix"),
        "author": "dev.team@example.com",
        "diff_summary": "Modified DB client config: max_pool_size changed to 50; lowered idle timeout"
    }
    # append to deploys file (json array)
    try:
        with open(DEPLOYS_FILE, "r+") as fh:
            arr = json.load(fh)
            arr.append(deploy)
            fh.seek(0)
            json.dump(arr, fh, ensure_ascii=False, indent=2)
            fh.truncate()
    except Exception:
        with open(DEPLOYS_FILE, "w") as fh:
            json.dump([deploy], fh, ensure_ascii=False, indent=2)

    # generate simple metrics lines (zabbix-like)
    # metric names: db.pool.used, db.connections, api.errors. Use JSONL with timestamp, host, metric, value
    metrics = []
    base_ts = _utc_now()
    for sec_offset in range(0, 600, 60):  # 10 sample points
        t = (base_ts - datetime.timedelta(seconds=sec_offset)).isoformat().replace("+00:00", "Z")
        # simulate spike for pool scenario
        if scenario == "pool":
            val = random.randint(40, 55) if sec_offset < 300 else random.randint(10, 30)
            metrics.append({"timestamp": t, "host": "db-prod-01", "metric": "db.pool.used", "value": val})
            metrics.append({"timestamp": t, "host": "api-prod-01", "metric": "api.errors.5m", "value": random.randint(20, 120)})
        elif scenario == "oom":
            metrics.append({"timestamp": t, "host": "api-prod-01", "metric": "system.memory.rss_gb", "value": random.uniform(6.5, 9.5)})
        else:
            metrics.append({"timestamp": t, "host": "api-prod-01", "metric": "api.errors.5m", "value": random.randint(0, 30)})

    with open(METRICS_FILE, "a") as fh:
        for m in metrics:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")

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
                out.append({"timestamp": None, "host": "unknown", "level": "INFO", "message": line})
    return out

def _load_metrics() -> List[Dict]:
    if not os.path.exists(METRICS_FILE):
        return []
    out = []
    with open(METRICS_FILE, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def search_logs(query: str, minutes: int = 30, limit: int = 200) -> List[Dict]:
    """
    Return recent log entries matching query or host token. Sorted recent -> older.
    """
    all_logs = _load_logs()
    if not all_logs:
        return []
    window_cutoff = _utc_now() - datetime.timedelta(minutes=minutes or 30)
    matches = []
    q = (query or "").lower()
    for rec in reversed(all_logs):  # newest first
        ts = _parse_iso(rec.get("timestamp"))
        # if timestamp exists and older than window, skip
        if ts and ts < window_cutoff:
            continue
        msg = rec.get("message", "").lower()
        host = rec.get("host", "").lower()
        if not q or q in msg or q in host:
            matches.append(rec)
        else:
            q_tokens = set(q.split())
            msg_tokens = set(msg.split())
            if q_tokens & msg_tokens:
                matches.append(rec)
        if len(matches) >= limit:
            break
    return matches

def fetch_deploys_stub(query: str = "", minutes: int = 60, limit: int = 10) -> List[Dict]:
    """
    Load deploy stubs and filter by query tokens (case-insensitive).
    """
    try:
        with open(DEPLOYS_FILE, "r") as fh:
            arr = json.load(fh)
            if not query:
                return arr[-limit:]
            q = query.lower()
            matches = []
            for d in arr:
                msg = d.get("message", "").lower()
                if q in msg or any(tok in msg for tok in q.split()):
                    matches.append(d)
            return matches[-limit:]
    except Exception:
        return []

def search_metrics(query: str = "", minutes: int = 30, limit: int = 200) -> List[Dict]:
    """
    Simple metric search: return metrics lines matching metric name or host.
    """
    all_metrics = _load_metrics()
    if not all_metrics:
        return []
    window_cutoff = _utc_now() - datetime.timedelta(minutes=minutes or 30)
    q = (query or "").lower()
    matches = []
    for rec in reversed(all_metrics):
        ts = _parse_iso(rec.get("timestamp"))
        if ts and ts < window_cutoff:
            continue
        metric = rec.get("metric", "").lower()
        host = rec.get("host", "").lower()
        if not q or q in metric or q in host or any(tok in metric for tok in q.split()):
            matches.append(rec)
        if len(matches) >= limit:
            break
    return matches

#
# Single collector that returns unified evidence items (server-side)
#
def collect_all_evidence(query: str = "", minutes: int = 30, sources: Optional[List[str]] = None, max_items: int = 50) -> List[Dict]:
    """
    sources: list of 'logs', 'deploys', 'metrics' or None for all.
    Returns items in descending priority (roughly recent & severe first). Each item:
      {id, type, text, timestamp}
    """
    sources = sources or ["logs", "deploys", "metrics"]
    evidence = []
    if "logs" in sources:
        logs = search_logs(query, minutes, limit=max_items)
        for i, l in enumerate(logs, start=1):
            evidence.append({
                "id": f"log#{i}",
                "type": "log",
                "text": l.get("message", "")[:2000],
                "timestamp": l.get("timestamp")
            })
    if "deploys" in sources:
        deploys = fetch_deploys_stub(query, minutes, limit=10)
        for i, d in enumerate(deploys, start=1):
            evidence.append({
                "id": f"git#{i}",
                "type": "git",
                "text": f"{d.get('message','')} - author:{d.get('author','unknown')} - diff_summary:{d.get('diff_summary','')}"[:2000],
                "timestamp": d.get("timestamp")
            })
    if "metrics" in sources:
        metrics = search_metrics(query, minutes, limit=50)
        for i, m in enumerate(metrics, start=1):
            evidence.append({
                "id": f"metric#{i}",
                "type": "metric",
                "text": f"{m.get('timestamp')} {m.get('host')} {m.get('metric')}={m.get('value')}",
                "timestamp": m.get("timestamp")
            })
    # lightweight de-dup: keep first occurrences by text hash
    seen = set()
    out = []
    for ev in evidence:
        key = (ev.get("type"), ev.get("text")[:120])
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
        if len(out) >= max_items:
            break
    return out
