# backend/app/main.py
import os
import time
from .config import load_env, azure_config, openai_key as get_openai_key
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from .collectors import search_logs, generate_sample_incident, fetch_deploys_stub
from .correlation import correlate_evidence
from .rag import init_rag_store, build_prompt_and_query
from .utils import validate_llm_output, attach_audit

load_env(override=True)  # make sure .env is loaded early and override any existing env vars
OPENAI_KEY = get_openai_key()
# Allow either OpenAI SaaS key OR Azure OpenAI configuration to be provided.
# If neither is present, fail fast with a clear message.
AZURE_ENDPOINT, AZURE_KEY, AZURE_DEPLOY, _AZURE_API_VERSION = azure_config()

if not OPENAI_KEY and not (AZURE_ENDPOINT and AZURE_KEY and AZURE_DEPLOY):
    raise RuntimeError(
        "No OpenAI credentials found: set OPENAI_API_KEY for OpenAI SaaS, "
        "or AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY|AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT|AZURE_OPENAI_DEPLOYMENT_NAME for Azure OpenAI"
    )

# init RAG store (embedding model / optional FAISS)
init_rag_store()

app = FastAPI(title="Sherlock PoC - Backend")

# NOTE: permissive CORS for PoC/hackathon only.
# Replace allow_origins with your precise frontend origin (e.g., http://10.0.0.5:3000) for tighter security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TriageRequest(BaseModel):
    query: str
    time_window_minutes: Optional[int] = 30
    max_evidence: Optional[int] = 6

class GenerateSampleRequest(BaseModel):
    scenario: Optional[str] = "pool"  # pool | oom | external
    count: Optional[int] = 10

@app.post("/generate_sample")
def generate_sample(req: GenerateSampleRequest):
    """
    Generate synthetic logs and deploy stubs for demo.
    """
    count = req.count or 10
    scenario = req.scenario or "pool"
    items = generate_sample_incident(scenario=scenario, count=count)
    return {"status": "ok", "generated": len(items), "scenario": scenario}

@app.get("/")
def root():
    """Simple health/status endpoint listing main available routes."""
    return {
        "status": "ok",
        "service": "sherlock-backend",
        "endpoints": [
            {"path": "/generate_sample", "method": "POST", "desc": "Generate demo logs/deploys"},
            {"path": "/triage", "method": "POST", "desc": "Main triage endpoint"},
            {"path": "/health", "method": "GET", "desc": "Health check (200)"},
        ]
    }

@app.get("/health")
def health():
    """Lightweight health endpoint that returns 200 when service is up."""
    return {"status": "ok", "time": int(time.time())}

@app.post("/triage")
def triage(req: TriageRequest):
    """
    Main triage endpoint.
    Steps:
     - search fabricated logs and fetch deploy stubs
     - build evidence list
     - correlate and rank
     - call OpenAI (RAG) with top-k evidence
     - validate and return JSON with audit metadata
    """
    start = time.time()
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query must be provided")

    # 1) Collectors
    logs = search_logs(req.query, req.time_window_minutes)
    deploys = fetch_deploys_stub(req.query, req.time_window_minutes)

    # build evidence items (id, type, text, ts)
    evidence_items = []
    # logs first
    for i, l in enumerate(logs, start=1):
        evidence_items.append({
            "id": f"log#{i}",
            "type": "log",
            "text": l.get("message", "")[:2000],
            "timestamp": l.get("timestamp")
        })
    # deploys
    for i, d in enumerate(deploys, start=1):
        evidence_items.append({
            "id": f"git#{i}",
            "type": "git",
            "text": d.get("message", "")[:2000],
            "timestamp": d.get("timestamp")
        })

    if not evidence_items:
        # No evidence found - return a helpful message
        latency = int((time.time() - start) * 1000)
        return {
            "hypothesis": "No relevant evidence found for the query.",
            "confidence": 20.0,
            "root_causes": [],
            "suggested_actions": [{"action": "Inspect logs and increase log density for the service", "risk": "low", "evidence": []}],
            "evidence_map": {},
            "audit": attach_audit(req.dict(), [], latency)
        }

    # 2) Correlate / Rank
    ranked = correlate_evidence(evidence_items, req.query)
    top_k = ranked[: req.max_evidence or 6]

    # 3) RAG + OpenAI
    try:
        llm_json = build_prompt_and_query(top_k, OPENAI_KEY)
    except Exception as e:
        # fallback minimal deterministic RCA if LLM call fails
        llm_json = {
            "hypothesis": "deterministic fallback: likely issue from top evidence",
            "confidence": 50.0,
            "root_causes": [{"cause": top_k[0]["text"][:200], "evidence": [top_k[0]["id"]]}],
            "suggested_actions": [{"action": "Investigate top evidence and logs", "risk": "low", "evidence": [top_k[0]["id"]]}],
            "evidence_map": {ev["id"]: ev["text"][:800] for ev in top_k}
        }

    # 4) Validate LLM output; if invalid, use fallback
    valid, reason = validate_llm_output(llm_json, [ev["id"] for ev in top_k])
    if not valid:
        # fallback
        llm_json = {
            "hypothesis": "fallback after invalid model output: inspect top evidence manually",
            "confidence": 45.0,
            "root_causes": [{"cause": top_k[0]["text"][:200], "evidence": [top_k[0]["id"]]}],
            "suggested_actions": [{"action": "Inspect the logs and recent commits", "risk": "low", "evidence": [top_k[0]["id"]]}],
            "evidence_map": {ev["id"]: ev["text"][:800] for ev in top_k}
        }

    latency = int((time.time() - start) * 1000)
    llm_json["audit"] = attach_audit(req.dict(), [ev["id"] for ev in top_k], latency)
    return llm_json
