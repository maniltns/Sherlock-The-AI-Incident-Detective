# backend/app/rag.py
import os
import json
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("rag")
logger.setLevel(logging.INFO)

# New SDK imports
# Import openai SDK lazily in the function to avoid hard dependency at module import time
from .config import load_env, azure_config, openai_key as get_openai_key, openai_saas_model

load_env(override=True)  # ensure any .env settings are available and override existing env vars
MODEL = None
MODEL_NAME = "all-MiniLM-L6-v2"
SKIP_EMB = os.getenv("SKIP_EMBEDDINGS", "0").lower() in ("1", "true")


def init_rag_store():
    """
    Optional embedding model initialization.
    """
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


def build_prompt_and_query(evidence_items, openai_key: Optional[str]):
    """
    Supports:
    - Azure OpenAI (preferred if AZURE_* vars are set)
    - OpenAI SaaS fallback (if OPENAI_API_KEY present)
    """

    # Load Azure/OpenAI config (support multiple variable names)
    azure_endpoint, azure_key, azure_deploy, azure_api_version = azure_config()

    # Normalize endpoint if present (ensure scheme, strip trailing slash)
    if azure_endpoint:
        azure_endpoint = azure_endpoint.strip()
        if azure_endpoint.endswith("/"):
            azure_endpoint = azure_endpoint[:-1]
        # add scheme if missing
        if not azure_endpoint.startswith("http://") and not azure_endpoint.startswith("https://"):
            azure_endpoint = "https://" + azure_endpoint

    def _resolve_hostname(url: str) -> bool:
        """Return True if hostname resolves, False otherwise."""
        try:
            parsed = urlparse(url)
            host = parsed.netloc or parsed.path
            if not host:
                return False
            # split out potential port
            host_only = host.split(":")[0]
            socket.getaddrinfo(host_only, None)
            return True
        except Exception:
            return False

    # Build prompt
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

    # If openai_key wasn't supplied, check env config
    if not openai_key:
        openai_key = get_openai_key()

    try:
        # ============================
        # 1) Azure OpenAI mode (preferred)
        # ============================
        if azure_endpoint and azure_key and azure_deploy:
            logger.info("Attempting Azure OpenAI endpoint: %s", azure_endpoint)

            if not _resolve_hostname(azure_endpoint):
                # DNS/host resolution failed - log helpful message and fall back
                logger.error(
                    "Azure endpoint hostname could not be resolved from container: %s.\n"
                    "Check AZURE_OPENAI_ENDPOINT in .env (should be a reachable URL like https://<resource>.openai.azure.com)"
                    , azure_endpoint
                )
                raise RuntimeError("Azure endpoint not resolvable")

            try:
                from openai import AzureOpenAI
            except Exception:
                raise RuntimeError('Azure OpenAI client not available (install openai package)')

            client = AzureOpenAI(
                api_key=azure_key,
                azure_endpoint=azure_endpoint,
                api_version=azure_api_version,
            )

            resp = client.chat.completions.create(
                model=azure_deploy,        # deployment name
                messages=messages,
                temperature=0.0,
                max_tokens=700
            )
        else:
            # ============================
            # 2) OpenAI SaaS fallback
            # ============================
            if not openai_key:
                raise RuntimeError("No valid OpenAI or Azure credentials found.")

            saas_model = openai_saas_model()
            logger.info("Using OpenAI SaaS model: %s", saas_model)

            try:
                from openai import OpenAI
            except Exception:
                raise RuntimeError('OpenAI client not available (install openai package)')
            client = OpenAI(api_key=openai_key)

            resp = client.chat.completions.create(
                model=saas_model,
                messages=messages,
                temperature=0.0,
                max_tokens=700
            )

        txt = resp.choices[0].message.content
        try:
            parsed = json.loads(txt)
        except Exception:
            parsed = _extract_json_from_text(txt)

        # attach evidence_map
        if "evidence_map" not in parsed:
            parsed["evidence_map"] = {ev["id"]: ev["text"][:800] for ev in evidence_items}

        return parsed

    except Exception as e:
        logger.exception("LLM call failed: %s", e)
        raise
