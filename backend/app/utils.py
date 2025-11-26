# backend/app/utils.py
import re
import json
from typing import List

EVIDENCE_ID_PATTERN = re.compile(r"^[a-z]+#\d+$")

def validate_llm_output(obj, allowed_ids: List[str]):
    """
    Validate that obj is a dict and contains required keys and that referenced evidence IDs exist.
    Returns (valid:bool, reason:str)
    """
    required = {"hypothesis", "confidence", "root_causes", "suggested_actions", "evidence_map"}
    if not isinstance(obj, dict):
        return False, "output not a dict"
    if not required.issubset(set(obj.keys())):
        return False, f"missing keys: {required - set(obj.keys())}"
    # evidence_map should be a dict, relax checks since we generate it
    evmap = obj.get("evidence_map", {})
    if not isinstance(evmap, dict):
        return False, "evidence_map not a dict"
    # check root_causes references
    rc = obj.get("root_causes", [])
    try:
        for r in rc:
            for eid in r.get("evidence", []):
                if eid not in allowed_ids:
                    return False, f"root_causes references unknown id {eid}"
    except Exception:
        return False, "root_causes malformed"
    return True, "ok"

def redact_text(text: str) -> str:
    """
    Minimal PII redaction: emails, tokens, long hex keys.
    """
    text = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\b[A-Fa-f0-9]{32,}\b", "[REDACTED_KEY]", text)
    return text

def attach_audit(request_payload, evidence_ids, latency_ms):
    return {
        "request": request_payload,
        "evidence_used": evidence_ids,
        "latency_ms": latency_ms
    }
