# AriesView — AI Document Intelligence for Commercial Real Estate

A working local implementation of the AriesView RAG pipeline: document
ingestion → OCR/parsing → semantic chunking → SBERT embedding → Weaviate
hybrid indexing → JWT-authenticated query API → self-hosted LLaMA generation
→ React chat UI. Everything runs on-machine; no document content touches an
external API.

## Architecture

```
INGESTION PATH
  React frontend upload → API gateway (JWT) → Ingestion service
    → raw file stored in Azure Blob Storage (Azurite locally; swap the
      connection string for a real Storage Account in production)
    → document type detection: native PDF → PyMuPDF | scanned → OCR
    → structured JSON written to Azure Blob Storage
    → semantic chunking (SBERT-guided, cosine threshold 0.75)
    → SBERT all-MiniLM-L6-v2 embeddings (384-dim) via embedding service
    → Weaviate (hybrid index: vectors + BM25)

QUERY PATH
  React frontend → API gateway
    → JWT validated (roles + portfolio access enforced at token level)
    → query embedded with the same SBERT model
    → Weaviate hybrid search → top-5 chunks
    → dedup filter (position_index overlap)
    → prompt: system message + numbered context blocks + user query
    → LLaMA 3.1 8B via Ollama (self-hosted)
    → grounded answer + source citations
```

## Services

| Service | Port | Stack |
|---|---|---|
| Frontend | 5173 | React (Vite) |
| API gateway | 3001 | Node.js/Express — auth, retrieval, dedup, prompt, LLM |
| Ingestion | 8002 | Python/FastAPI — parsing, chunking, indexing |
| Embedding | 8001 | Python/FastAPI — sentence-transformers all-MiniLM-L6-v2 |
| Weaviate | 8080 | Docker — hybrid vector + BM25 store |
| Azurite | 10000 | Docker — Azure Blob Storage emulator (real `azure-storage-blob` SDK) |
| LLM | 11434 | Ollama serving `llama3.2:3b` (default; `OLLAMA_MODEL=llama3.1:8b` on 16GB+ machines) |

## Prerequisites

- Docker Desktop
- Ollama with a model pulled: `ollama pull llama3.2:3b` (default — sized for
  8GB RAM; on 16GB+ use `ollama pull llama3.1:8b` and set
  `OLLAMA_MODEL=llama3.1:8b` to match production sizing)
- Node.js 18+, Python 3.11+

## Setup

```bash
# Python services
python3 -m venv .venv
.venv/bin/pip install sentence-transformers fastapi "uvicorn[standard]" \
  pymupdf weaviate-client python-multipart httpx pytest numpy azure-storage-blob

# Node services
(cd services/api-gateway && npm install)
(cd frontend && npm install)
```

Optional OCR path for scanned PDFs: `pip install paddleocr paddlepaddle`.
Native PDFs work without it.

## Run

```bash
./scripts/dev.sh     # starts everything; logs in ./logs/
./scripts/stop.sh    # stops everything
```

Open http://localhost:5173 and sign in:

| User | Password | Access |
|---|---|---|
| `analyst` | `demo` | `demo-portfolio` only (role-based access) |
| `admin` | `demo` | all portfolios |

Generate and ingest the sample CRE documents:

```bash
.venv/bin/python sample_docs/generate_samples.py
TOKEN=$(curl -s -X POST localhost:3001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"analyst","password":"demo"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -X POST localhost:3001/upload -H "Authorization: Bearer $TOKEN" \
  -F file=@sample_docs/Lease_Agreement_TenantA.pdf
curl -s -X POST localhost:3001/upload -H "Authorization: Bearer $TOKEN" \
  -F file=@sample_docs/Offering_Memorandum_CongressTower.pdf
```

Then ask in the UI (or via `POST /query`):
- "Can the tenant terminate the lease early, and what does it cost?"
- "What is the asking cap rate for Congress Tower?"
- "When does the security deposit get returned?"

## Tests

```bash
.venv/bin/pytest tests/                    # semantic chunker
(cd services/api-gateway && npm test)      # dedup filter + prompt assembly
```

## Key design decisions (mirrors production)

- **Self-hosted LLM** — CRE documents contain cap rates, deal structures,
  investor returns; nothing leaves private infrastructure.
- **Semantic chunking at 0.75** — boundaries at meaning shifts, not
  character counts, so multi-paragraph legal clauses stay intact.
- **Same SBERT model at ingestion and query time** — both vectors must live
  in the same 384-dim space for cosine similarity to be meaningful.
- **Weaviate hybrid search** — "SNDA" and "estoppel" need exact keyword
  (BM25) matching alongside semantic similarity.
- **k=5 with dedup** — over-fetch 10, dedupe position_index overlaps, send
  the top 5 as numbered, source-labeled context blocks.
- **Warm processes** — models stay loaded in memory (no serverless cold
  starts); locally Ollama and the embedding service stay resident.

## Local stand-ins for the production Azure stack

| Production | Local |
|---|---|
| Azure Blob Storage | Azurite (real `azure-storage-blob` SDK against the official emulator — swap the connection string for a real Storage Account, no code changes) |
| Azure AD + JWKS validation | Local JWT issuance/validation with identical claim shape |
| LLaMA 3.1 8B on Azure VM | LLaMA 3.1 8B via Ollama |
| GitLab CI/CD + Portainer | GitHub Actions (`.github/workflows/ci.yml`) / `docker-compose.yml` |
