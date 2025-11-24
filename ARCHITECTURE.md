## Architecture Diagra

![alt text](Architecture-1.svg)

## Project structure

```
sherlock-simple/
├─ backend/
│  ├─ app/
│  │  ├─ main.py          # FastAPI server
│  │  ├─ rag.py           # RAG + OpenAI / Azure integration
│  │  ├─ collectors.py    # synthetic log & deploy generators, search
│  │  ├─ correlation.py   # simple ranking/correlation logic
│  │  ├─ utils.py         # validation + audit helpers
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ model_data/         # persisted demo logs + deploy stubs (bind-mounted)
├─ frontend/
│  ├─ (React + static build served via nginx)
│  └─ Dockerfile
├─ docker-compose.yml
└─ .env
```

## Notes / How components interact

- Frontend sends queries to Backend (`/triage`) and displays results.
- Backend collects logs from `model_data/` (or generated via `/generate_sample`), correlates evidence, and (optionally) calls an LLM via `rag.py`.
- LLM calls use either Azure OpenAI (preferred if AZURE_* env vars present) or OpenAI SaaS (if `OPENAI_API_KEY` present). Use `SKIP_EMBEDDINGS=1` to avoid heavy ML dependencies.
- Docker Compose orchestrates `frontend` and `backend` services and mounts `model_data` as a persistent volume.

## How to view the SVG diagram

- Open `ARCHITECTURE.svg` in your file manager or a browser:
