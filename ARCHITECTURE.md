# Architecture Diagram (Mermaid)

Below are two representations: a Mermaid diagram you can render in tools that support Mermaid, and the project tree.

## Mermaid (renderable)

```mermaid
flowchart LR
  subgraph User
    U[User / Operator\n(Browser / CLI)]
  end

  subgraph Frontend
    F[Frontend (nginx)\nStatic UI\nPort 3000]
  end

  subgraph Backend
    B[Backend (FastAPI)\nPort 8000]
    subgraph Services
      C[collectors.py\n(logs + deploys)]
      R[correlation.py\n(ranking)]
      G[rag.py\n(OpenAI / Azure)]
      UTL[utils.py\n(validation + audit)]
    end
  end

  subgraph Data[model_data/ volume]
    M(sample_logs.jsonl\ndeploys.json)
  end

  subgraph External[External AI Services]
    AZ(Azure OpenAI)
    SA(OpenAI SaaS)
  end

  U --> F
  F --> B
  B --> C
  B --> R
  B --> G
  C --> M
  R --> M
  G --> AZ
  G --> SA
  B ---|volume| M
  
  classDef infra fill:#eef2ff,stroke:#3b82f6
  class Frontend,Backend,Data,External infra
```

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

```bash
# from repo root (Linux)
xdg-open ARCHITECTURE.svg || echo "Open ARCHITECTURE.svg with a browser or image viewer"
```

- Or render the Mermaid block above using a Mermaid renderer (VS Code extension, GitHub preview, or online tool at https://mermaid.live).

---

If you want, I can also export a PNG of the SVG, or add this diagram into the README. Which format would you like next? 
