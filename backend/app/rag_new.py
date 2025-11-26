"""
Alternative split file to stage a clean `rag` implementation.
Will replace the broken `rag.py` once verified.
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

load_env(override=True)

MODEL = None
MODEL_NAME = "all-MiniLM-L6-v2"
SKIP_EMB = os.getenv("SKIP_EMBEDDINGS", "0").lower() in ("1", "true")


def init_rag_store():
    global MODEL
    if SKIP_EMB:
        logger.info("SKIP_EMBEDDINGS set -> Skipping embedding init.")
        return
    try:
        from sentence_transformers import SentenceTransformer
        MODEL = SentenceTransformer(MODEL_NAME)
        logger.info("Loaded embedding model")
    except Exception as e:
        logger.exception("Embedding load failed: %s", e)
        MODEL = None


def _extract_json_from_text(text: str):
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


def _mask_key(k: str):
    if not k:
        return None
    k = str(k)
    if len(k) <= 8:
        return k[:1] + '...' + k[-1:]
    return k[:4] + '...' + k[-4:]


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
    azure_endpoint, azure_key, azure_deploy, azure_api_version = azure_config()

    if azure_endpoint:
        azure_endpoint = azure_endpoint.strip()
        if azure_endpoint.endswith("/"):
            azure_endpoint = azure_endpoint[:-1]
        if not azure_endpoint.startswith("http://") and not azure_endpoint.startswith("https://"):
            azure_endpoint = "https://" + azure_endpoint

    evidence_text = ""
    for ev in evidence_items:
        evidence_text += f"{ev['id']}: {ev['type']} — {ev['text'][:800]}\n\n"

    system_prompt = (
        "You are Sherlock — an incident triage assistant. Only use evidence provided. "
        "Return JSON with hypothesis, confidence, root_causes, suggested_actions, evidence_map."
    )
    user_prompt = f"Evidence:\n{evidence_text}\n\nQuestion: Generate RCA JSON."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if not openai_key:
        openai_key = get_openai_key()

    max_attempts = 2
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        logger.info("LLM call attempt %d/%d", attempt, max_attempts)
        try:
            # Try Azure first
            if azure_endpoint and azure_key and azure_deploy:
                logger.info("Attempting Azure OpenAI: %s (%s)", azure_endpoint, azure_deploy)
                if not _resolve_hostname(azure_endpoint):
                    raise RuntimeError("Azure endpoint not resolvable")
                try:
                    from openai import AzureOpenAI, AuthenticationError as OpenAIAuthError
                except Exception:
                    raise RuntimeError('Azure OpenAI client not available (install openai package)')
                client = AzureOpenAI(api_key=azure_key, azure_endpoint=azure_endpoint, api_version=azure_api_version)
                try:
                    resp = client.chat.completions.create(model=azure_deploy, messages=messages, temperature=0.0, max_tokens=700)
                except OpenAIAuthError as e:
                    logger.error("Azure auth failed: %s", e)
                    # Try SaaS fallback
                    fallback = get_openai_key()
                    if fallback:
                        from openai import OpenAI
                        client = OpenAI(api_key=fallback)
                        resp = client.chat.completions.create(model=openai_saas_model(), messages=messages, temperature=0.0, max_tokens=700)
                    else:
                        raise
            else:
                if not openai_key:
                    raise RuntimeError("No credentials for Azure or OpenAI SaaS")
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                resp = client.chat.completions.create(model=openai_saas_model(), messages=messages, temperature=0.0, max_tokens=700)

            txt = resp.choices[0].message.content
            try:
                parsed = json.loads(txt)
            except Exception:
                parsed = _extract_json_from_text(txt)

            if "evidence_map" not in parsed:
                parsed["evidence_map"] = {ev["id"]: ev["text"][:800] for ev in evidence_items}
            return parsed
        except Exception as e:
            last_exc = e
            logger.exception("LLM attempt %d failed: %s", attempt, e)
            if attempt < max_attempts:
                messages.append({"role": "user", "content": "IMPORTANT: Please return ONLY a single valid JSON object and nothing else."})
            continue
    raise last_exc if last_exc else RuntimeError("LLM calls failed for unknown reasons")


def validate_azure_credentials():
    azure_endpoint, azure_key, azure_deploy, azure_api_version = azure_config()
    if not (azure_endpoint and azure_key and azure_deploy):
        return False, "no_azure_credentials"
    try:
        from openai import AzureOpenAI, AuthenticationError as OpenAIAuthError
    except Exception:
        return False, "openai-sdk-missing"
    try:
        client = AzureOpenAI(api_key=azure_key, azure_endpoint=azure_endpoint, api_version=azure_api_version)
        resp = client.chat.completions.create(model=azure_deploy, messages=[{"role":"system","content":"Ping."}], temperature=0.0, max_tokens=1)
        return True, "ok"
    except OpenAIAuthError as e:
        return False, f"auth_error: {e}"
    except Exception as e:
        return False, f"error: {e}"
