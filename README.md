# Sherlock PoC - Incident Triage with RAG

A small proof-of-concept incident triage system (backend + frontend) demonstrating lightweight log collectors, evidence correlation, and an LLM-based root-cause analysis (RAG) pipeline.

This updated README documents repository structure, runtime environment variables, how to run and debug the app (Docker and local), and a short demo walkthrough with key insights.

---

## Highlights
- Lightweight FastAPI backend (`backend/`) for collectors, correlation, and LLM-based RCA
- Static front-end served via Nginx (`frontend/static`) to demo the UX
- LLM integration supports both Azure OpenAI (preferred) and OpenAI SaaS (fallback)
- Configurable `.env` and `docker-compose` for quick local setups
- Debug endpoints to inspect credential availability and run minimal validations

---
**Project layout**
- `backend/`: FastAPI backend service (main application code, Dockerfile, requirements)
- `frontend/`: Static/frontend code for UI (served separately)
- `model_data/`: Example data used by backend (deploy stubs and sample logs)
- `docker-compose.yml`: Compose configuration for running both services together

## Notes / How components interact

- Frontend sends queries to Backend (`/triage`) and displays results.
- Backend collects logs from `model_data/` (or generated via `/generate_sample`), correlates evidence, and (optionally) calls an LLM via `rag.py`.
- LLM calls use either Azure OpenAI (preferred if AZURE_* env vars present) or OpenAI SaaS (if `OPENAI_API_KEY` present). Use `SKIP_EMBEDDINGS=1` to avoid heavy ML dependencies.
- Docker Compose orchestrates `frontend` and `backend` services and mounts `model_data` as a persistent volume.

**Prerequisites**
- Docker and Docker Compose installed on your machine.
- Optional: an OpenAI API key (for OpenAI SaaS) or Azure OpenAI resource (endpoint, key, deployment) if you want live LLM responses.
---
## Repo structure
```
sherlock-simple/
├─ backend/
│  ├─ app/
│  │  ├─ main.py          # FastAPI server and endpoints
│  │  ├─ rag.py           # LLM integration + Azure/SaaS fallback + retries
│  │  ├─ collectors.py    # synthetic log & deploy generators, search
│  │  ├─ correlation.py   # evidence scoring & ranking logic
│  │  ├─ utils.py         # validation + redaction + audit helpers
│  ├─ Dockerfile
│  ├─ requirements.txt
  └─ model_data/         # persistent demo logs + deploy stubs (mounted)
├─ frontend/
│  ├─ static/            # static HTML/JS/UX demo; Nginx Dockerfile to serve
├─ docker-compose.yml
└─ .env                  # local env file for OpenAI / Azure credentials
```

---
---
## Architecture Diagram

![alt text](Architecture-1.svg)
---

## What it does
- Generate synthetic logs, deploy metadata, and metrics for demos (`/generate_sample`).
- Search logs, deploys, and metrics for a query (`collectors.search_logs`, `collectors.fetch_deploys_stub`, `collectors.search_metrics`).
- Rank correlated evidence using `correlation.correlate_evidence` (recency, severity, token overlap).
- Build a prompt and call an LLM (Azure OpenAI preferred, fallback to OpenAI SaaS) in `rag.build_prompt_and_query`.
- Validate LLM output with `utils.validate_llm_output` and attach audit metadata.

---

## Key Endpoints
- `GET /` - Health & endpoints
- `POST /generate_sample` - Generate synthetic logs, deploys, and metrics (demo scenarios) 
- `POST /triage` - Main endpoint: accepts request JSON `{query, time_window_minutes, max_evidence}` and returns a structured RCA JSON
- `GET /health` - 200 status health endpoint
- `GET /debug/credentials` - Non-secret view of configured credentials and key fingerprints (helpful when debugging Azure 401s)
- `GET /debug/validate_credentials` - Runs a minimal test against Azure/OpenAI SDK to verify keys and returns lightweight diagnostics

---

## Environment variables (.env)
Create a file named `.env` in the project root to configure keys and settings. Example:
```
AZURE_OPENAI_ENDPOINT=https://kraft016.openai.azure.com
AZURE_OPENAI_API_KEY=<AZURE_KEY>
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview
SKIP_EMBEDDINGS=1
ENABLE_RAPTOR_MINI=1  # optional; prefer raptor-mini for SaaS
OPENAI_API_KEY=<OPENAI_SAAS_KEY>  # only if using OpenAI SaaS
```

Notes:
- Azure vars: If `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_DEPLOYMENT_NAME` are present, the backend will prefer Azure OpenAI.
- OpenAI SaaS: If `OPENAI_API_KEY` is present, the backend can call SaaS OpenAI.
- `SKIP_EMBEDDINGS=1` avoids heavy ML deps (sentence-transformers/torch/faiss) and is recommended for quick dev.

Security Reminder: Never commit or push API keys. Store them in a secret manager or CI/CD vault in real deployments.

---

## Running locally

We provide two recommended workflows: Docker Compose (fast and reproducible) and a local Python virtual environment (dev iteration).

### Docker Compose (recommended)
1. Build and start services:
```bash
docker compose up --build
```
2. Or run in background:
```bash
docker compose up -d --build
```
3. Monitor backend logs:
```bash
docker compose logs -f backend
```
4. Backend UI & endpoints available:
  - Backend: `http://localhost:8000`
  - Frontend: `http://localhost:3000`

### Single backend container (Docker only)
1. Build image:
```bash
cd backend
docker build -t sherlock-backend:local .
```
2. Run image (minimal runtime config):
```bash
docker run --rm -d -p 8000:8000 \
  --env-file ../.env \
  -e SKIP_EMBEDDINGS=1 \
  -v "$(pwd)/model_data":/app/model_data \
  --name sherlock-backend sherlock-backend:local
```

### Local Python (for dev)
1. Create virtualenv and install dependencies:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```
2. Set `.env` or export necessary env vars (example):
```bash
export SKIP_EMBEDDINGS=1
export OPENAI_API_KEY="<OPENAI_SAAS_KEY>"
# or Azure variables for Azure OpenAI
```
3. Start backend with `uvicorn` and auto-reload for code changes:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
4. For the front-end, it is static. You can either run the container via docker compose or serve `frontend/static` with a static server while developing.

---

## Demo Walkthrough (minimal)
1. Start the system (via Docker Compose recommended):
```bash
docker compose up -d --build
```
2. Generate demo logs and deploy:
```bash
curl -X POST http://localhost:8000/generate_sample \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"pool","count":5}'
```
3. Run triage for a sample query and view the output:
```bash
curl -X POST http://localhost:8000/triage \
  -H 'Content-Type: application/json' \
  -d '{"query":"connection pool exhausted","time_window_minutes":60}'
```
4. Use UI controls to generate samples and run triage from the frontend (http://localhost:3000).

---

## Debugging & Troubleshooting
- `GET /debug/credentials` shows non-secret status (presence of keys and a masked fingerprint). Useful when backend shows `401` from Azure.
- `GET /debug/validate_credentials` will attempt a minimal request to Azure / OpenAI SaaS to validate credentials and surface `auth_error` or `ok` responses.
- Common issues:
  - `401 Access denied` from Azure: usually a mismatched API key / deployment name. Use the curl test below (replace values) to test:
```bash
curl -s -X POST "https://<ENDPOINT>/openai/deployments/<DEPLOYMENT>/chat/completions?api-version=<API_VERSION>" \
  -H "api-key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"system","content":"ping"}], "max_tokens":1}' | jq .
```
  - DNS/hostname not resolvable: ensure container DNS or endpoint is reachable. Docker Compose sets `dns: 8.8.8.8` and `1.1.1.1` by default.
  - Rapid rebuilds: use `SKIP_EMBEDDINGS=1` to prevent heavy model downloads.

## Implementation details & design
- Evidence generation & storage: `backend/app/collectors.py` stores logs and deploy stubs under `model_data/` (persisted volume).
- Evidence ranking: `backend/app/correlation.py` uses severity, token overlap, recency, and type-weight heuristics to rank evidence.
- LLM integration: `backend/app/rag.py` prefers Azure OpenAI (endpoint/key/deployment) and will fall back to OpenAI SaaS if Azure auth fails (with a provided SaaS key). The module:
  - Builds a structured system + user prompt from the top-ranked evidence
  - Attempts the LLM call with two attempts (the second appends a strict `JSON-only` instruction)
  - Extracts and validates JSON; attaches `evidence_map` and minimal `audit` info
- LLM output validation: `backend/app/utils.py::validate_llm_output` requires the response include keys `hypothesis`, `confidence`, `root_causes`, `suggested_actions`, `evidence_map`, `impact`. If the LLM output isn't valid, the backend returns a deterministic fallback message.

---

## Development & Contribution tips
- Use `.env` to avoid leaking secrets in Docker Compose or git.
- To speed local dev, enable `SKIP_EMBEDDINGS=1`, which removes heavy ML dependencies.
- Consider keeping a `requirements-dev.txt` for local tooling & linting.

## Next steps / Optional improvements
- Add unit tests for `collectors` and `correlation` functions.
- Add CI linting and test runners.
- Add a small `demo.sh` to automate the demo flow described above.
- Expand LLM parsing and schema relaxations to tolerate more varied outputs or add an in-process JSON fallback sanitizer.

---

## License
This is a PoC — use for learning & experimentation only.
---
*** End of README ***

