# backend/app/rag.py
"""
Clean RAG + improved SRE-style RCA prompting
"""
import os
import json
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("rag")
logger.setLevel(logging.INFO)

from .config import load_env, azure_config, openai_key as get_openai_key, openai_saas_model

load_env(path='../.env', override=True)

SKIP_EMB = os.getenv("SKIP_EMBEDDINGS", "0").lower() in ("1", "true")

def _mask_key(k: str):
    if not k:
        return None
    k = str(k)
    if len(k) <= 8:
        return k[:1] + '...' + k[-1:]
    return k[:4] + '...' + k[-4:]

def _extract_json_from_text(text: str):
    # extract first JSON object from a text blob
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object in output")
    stack = 0
    end = None
    for i in range(start, len(text)):
        if text[i] == "{":
            stack += 1
        elif text[i] == "}":
            stack -= 1
            if stack == 0:
                end = i
                break
    if end is None:
        raise ValueError("Unbalanced JSON")
    return json.loads(text[start:end+1])

def _resolve_hostname(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        if not host:
            return False
        host_only = host.split(":")[0]
        socket.getaddrinfo(host_only, None)
        return True
    except Exception:
        return False

def build_prompt_and_query(evidence_items, openai_key: Optional[str]):
    """
    Build SRE-style prompt and query backend LLM (Azure or OpenAI SaaS).
    Returns parsed JSON with keys: hypothesis, confidence, root_causes, suggested_actions, evidence_map
    """
    azure_endpoint, azure_key, azure_deploy, azure_api_version = azure_config()
    if azure_endpoint:
        azure_endpoint = azure_endpoint.strip().rstrip("/")
        if not azure_endpoint.startswith("http"):
            azure_endpoint = "https://" + azure_endpoint

    evidence_text = ""
    for ev in evidence_items:
        evidence_text += f"{ev['id']}: {ev['type']} — {ev['text'][:1000]}\n"

    system_prompt = (
        "You are Sherlock, an SRE/Incident Triage assistant. Produce a single valid JSON object ONLY. "
        "This JSON must follow the enterprise RCA schema exactly and be grounded to the provided evidence. "
        "Do NOT fabricate evidence IDs; only reference the IDs provided in the evidence map.\n\n"
        "Required JSON schema (keys):\n"
        " - hypothesis: short summary string (1-2 sentences)\n"
        " - confidence: integer 0-100\n"
        " - impact: short bullet-style string describing affected services/customers\n"
        " - root_causes: array of objects {cause: string, evidence: [id,...], probability: 0-100}\n"
        " - contributing_factors: array of short strings\n"
        " - suggested_actions: array of objects {action: string, type: 'mitigate'|'fix'|'monitor'|'rollback', risk: 'low'|'medium'|'high', eta_minutes: integer or null, evidence: [id,...], rollback_plan: optional string}\n"
        " - evidence_map: object mapping evidence id -> text summary\n\n"
        "IMPORTANT: Return ONLY the JSON object. No surrounding text, code fences, or explanation."
    )

    user_prompt = f"Evidence:\n{evidence_text}\n\nProduce RCA JSON per schema above."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if not openai_key:
        openai_key = get_openai_key()

    last_exc = None
    for attempt in range(1, 3):
        logger.info("LLM call attempt %d", attempt)
        try:
            # prefer Azure if present
            if azure_endpoint and azure_key and azure_deploy:
                if not _resolve_hostname(azure_endpoint):
                    raise RuntimeError("Azure endpoint not resolvable")
                from openai import AzureOpenAI, AuthenticationError as OpenAIAuthError
                client = AzureOpenAI(api_key=azure_key, azure_endpoint=azure_endpoint, api_version=azure_api_version)
                resp = client.chat.completions.create(model=azure_deploy, messages=messages, temperature=0.0, max_tokens=900)
            else:
                if not openai_key:
                    raise RuntimeError("No credentials for Azure or OpenAI SaaS")
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                resp = client.chat.completions.create(model=openai_saas_model(), messages=messages, temperature=0.0, max_tokens=900)

            txt = resp.choices[0].message.content
            try:
                parsed = json.loads(txt)
            except Exception:
                parsed = _extract_json_from_text(txt)

            # Always attach evidence_map from our server-side evidence_items (defensive)
            parsed["evidence_map"] = {ev["id"]: ev["text"][:800] for ev in evidence_items}
            # normalize confidence to int
            try:
                parsed["confidence"] = int(parsed.get("confidence", 0))
            except Exception:
                parsed["confidence"] = 0
            return parsed
        except Exception as e:
            last_exc = e
            logger.exception("LLM attempt failed: %s", e)
            # on failure, append user hint to be stricter
            messages.append({"role": "user", "content": "Return EXACTLY a single JSON object matching the schema and nothing else."})
            continue
    raise last_exc if last_exc else RuntimeError("LLM calls failed")
