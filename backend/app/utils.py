# backend/app/utils.py
import re
import json
from typing import List

EVIDENCE_ID_PATTERN = re.compile(r"^[a-z]+#\d+$")

def validate_llm_output(obj, allowed_ids: List[str]):
    """
    Validate that obj matches minimal expected keys and evidence references.
    """
    required = {"hypothesis", "confidence", "root_causes", "suggested_actions", "evidence_map", "impact"}
    if not isinstance(obj, dict):
        return False, "output not a dict"
    if not required.issubset(set(obj.keys())):
        return False, f"missing keys: {required - set(obj.keys())}"
    evmap = obj.get("evidence_map", {})
    if not isinstance(evmap, dict):
        return False, "evidence_map not a dict"
    # check references in root_causes and suggested_actions
    try:
        for r in obj.get("root_causes", []):
            for eid in r.get("evidence", []):
                if eid not in allowed_ids:
                    return False, f"root_causes references unknown id {eid}"
        for a in obj.get("suggested_actions", []):
            for eid in a.get("evidence", []):
                if eid not in allowed_ids:
                    return False, f"suggested_actions references unknown id {eid}"
    except Exception:
        return False, "malformed root_causes or suggested_actions"
    return True, "ok"

def redact_text(text: str) -> str:
    text = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\b[A-Fa-f0-9]{32,}\b", "[REDACTED_KEY]", text)
    return text

def attach_audit(request_payload, evidence_ids, latency_ms):
    return {
        "request": request_payload,
        "evidence_used": evidence_ids,
        "latency_ms": latency_ms
    }
