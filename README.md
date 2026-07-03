# NeuroScan AI — Agent-Based Alzheimer's Stage Prediction

An end-to-end clinical decision-support system that predicts a patient's
Alzheimer's stage (**Normal / MCI / AD**) from a brain **MRI**, a **synthetic PET**
image, an interactive **cognitive test**, and **blood-report / clinical** data — then
stores everything in a **Neo4j knowledge graph** and explains results with
**GraphRAG** (retrieval-augmented generation over a vector index, answered by
**Google Gemini** or a deterministic fallback).

> ⚕️ Educational / research project (BMSCE, 6th sem AIML). Outputs are decision
> support, **not** a medical diagnosis.

---

## Architecture

```
                         ┌──────────────────────── FRONTEND (React + Vite) ───────────────────────┐
                         │  Dashboard · Patients · Scan Upload · MRI→PET · Blood Reports ·         │
                         │  Cognitive Test · Prediction · Digital Twin · Ask AI (GraphRAG panel)    │
                         └───────────────────────────────┬────────────────────────────────────────┘
                                                         │ REST (axios)
                         ┌───────────────────────────────▼────────────────────────────────────────┐
                         │                      BACKEND (FastAPI)                                   │
                         │                                                                          │
                         │   LangGraph pipeline:  validate ─▶ predict ─▶ reason(RAG) ─▶ END         │
                         │                                                                          │
                         │   Agent 2 (GAN MRI→PET) · Agent 3 (cognitive test) ·                     │
                         │   Agent 1 (feature fusion + MLP classifier) · Grad-CAM · Digital Twin    │
                         │   OCR (PaddleOCR) → clinical field parser                                │
                         └───────────┬───────────────────────────────────────┬─────────────────────┘
                                     │                                        │
                    ┌────────────────▼───────────────┐        ┌───────────────▼──────────────────┐
                    │   Neo4j KNOWLEDGE GRAPH         │        │   GraphRAG                        │
                    │   Patient ─▶ Visit ─▶ Scan /    │        │   • sentence-transformers embeds  │
                    │   Prediction / Report / Twin …  │◀──────▶│     clinical knowledge            │
                    │   + NATIVE VECTOR INDEX over    │        │   • Neo4j vector search (top-k)   │
                    │     KnowledgeChunk.embedding    │        │   • Gemini / templated answer     │
                    └─────────────────────────────────┘        └───────────────────────────────────┘
                            (auto-fallback to CSV store if Neo4j is unavailable)
```

**Chosen architecture:** **GraphRAG + LangGraph**, with the **vector store living
inside Neo4j** (native vector index) so the knowledge graph *and* the vector
storage are one system. This satisfies both the "knowledge graph" and
"vector storage" requirements without a second database.

| Concern | Technology |
|---|---|
| Storage / knowledge graph | **Neo4j 5** (Docker), auto-fallback to CSV |
| Vector storage | **Neo4j native vector index** (`clinical_chunks`, 384-dim, cosine) |
| Embeddings | **sentence-transformers** `all-MiniLM-L6-v2` (local, no key) |
| Orchestration | **LangGraph** `StateGraph` (validate → predict → reason) |
| RAG answers | **Google Gemini** (`gemini-flash-latest`) with templated fallback |
| ML | PyTorch — GAN (MRI→PET), ResNet features, MLP classifier, Grad-CAM |
| OCR | PaddleOCR + regex clinical parser |
| API | FastAPI · Frontend: React + Vite + Tailwind |

---

## Prerequisites

- **Python 3.11**, **Node 18+**, **Docker Desktop**
- ~2 GB free disk (Neo4j image + embedding model)

---

## Quick start

### 1. Start the Neo4j knowledge graph (Docker)

```bash
# from the project root (where docker-compose.yml lives)
docker compose up -d
# wait ~20-30s for Neo4j to become healthy
docker compose logs -f neo4j     # optional: watch until "Started"
```

- Browser UI: <http://localhost:7474>  (login `neo4j` / the `NEO4J_PASSWORD` in `.env`)
- Bolt (used by the app): `bolt://localhost:7687`

> First run: copy `.env.example` to `.env` and set `NEO4J_PASSWORD` (min 8 chars).
> The default `.env` already uses `password`.

### 2. Backend

```bash
cd alzheimer-prediction-system
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r backend/requirements.txt

# migrate existing CSV records into the graph (idempotent)
python scripts/migrate_csv_to_neo4j.py

# embed the clinical knowledge base into the vector index (also runs on startup)
python scripts/seed_vector_store.py

# run the API
uvicorn backend.main:app --reload --port 8000
```

API docs: <http://localhost:8000/docs>

### 3. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

### 4. (Optional) Enable Gemini for LLM-written answers

Get a free key at <https://aistudio.google.com/app/apikey>, then in `.env`:

```
GEMINI_API_KEY=your_key_here
```

Restart the backend. Without a key, the RAG layer returns solid **templated**
answers, so the app is fully functional offline.

---

## How storage routing works

`backend/knowledge_graph/patient_store.py` picks a backend once per process:

1. `GRAPH_BACKEND=neo4j` and Neo4j reachable → **Neo4j knowledge graph**.
2. Neo4j down and `ALLOW_CSV_FALLBACK=True` → **CSV store** (`data/csv_db/*.csv`).
3. `GRAPH_BACKEND=csv` or `USE_CSV_FALLBACK=True` → **CSV** directly.

This means the app never crashes just because you forgot to start Docker.

---

## GraphRAG API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET`  | `/api/rag/status` | Active backend, vector-index state, LLM provider |
| `POST` | `/api/rag/seed` | (Re)embed the clinical knowledge base |
| `POST` | `/api/rag/ask` | `{patient_id, question}` → grounded answer + sources |
| `GET`  | `/api/rag/explain/{patient_id}` | Explain the patient's latest predicted stage |

Example:

```bash
curl -X POST http://localhost:8000/api/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"PAT-D6CBDC3C","question":"Why is this patient MCI and what should we monitor?"}'
```

The answer is grounded in (a) that patient's **graph facts** (stage, cognitive
index, blood data) and (b) the **top-k retrieved** clinical knowledge chunks.

In the UI, open a patient and use the **"Ask AI about this patient"** panel
(bottom of the profile) — it calls these endpoints and shows the answer, the
provider used (Gemini vs templated), and the retrieved source chunks.

---

## Project layout

```
alzheimer-prediction-system/
├── docker-compose.yml            # Neo4j 5 + APOC + vector index
├── .env / .env.example
├── scripts/
│   ├── migrate_csv_to_neo4j.py   # CSV → knowledge graph migration
│   └── seed_vector_store.py      # embed knowledge base into vector index
├── synthetic_blood_reports/      # OCR test fixtures (see its README)
├── backend/
│   ├── main.py                   # FastAPI app + routers + startup seeding
│   ├── config.py                 # settings (Neo4j / RAG / Gemini)
│   ├── agents/
│   │   ├── agent1..4_*.py        # data proc, PET synth, cognitive, orchestrator
│   │   └── graph_pipeline.py     # LangGraph StateGraph orchestration
│   ├── knowledge_graph/
│   │   ├── neo4j_client.py       # driver + constraints
│   │   ├── neo4j_store.py        # graph CRUD (mirrors csv_fallback API)
│   │   ├── csv_fallback.py       # CSV dev store (fallback)
│   │   ├── patient_store.py      # backend router (neo4j ⇄ csv)
│   │   └── medication_mapper.py  # evidence-based medication rules
│   ├── rag/
│   │   ├── embeddings.py         # sentence-transformers wrapper
│   │   ├── knowledge_base.py     # curated clinical knowledge chunks
│   │   ├── vector_store.py       # Neo4j native vector index
│   │   └── graph_rag.py          # retrieve + ground + generate
│   ├── llm/gemini_client.py      # Gemini with templated fallback
│   ├── models/                   # GAN, classifier, OCR, report generator
│   └── api/routes/               # patients, scans, predictions, cognitive, twin, reports, rag
└── frontend/                     # React + Vite UI
```

---

## Inspecting the knowledge graph

Open <http://localhost:7474> and try:

```cypher
// full patient graph
MATCH (p:Patient)-[r]->(n) RETURN p, r, n LIMIT 100

// one patient's predictions over time
MATCH (:Patient {patient_id:'PAT-D6CBDC3C'})-[:HAS_PREDICTION]->(pr:Prediction)
RETURN pr.run_date, pr.stage, pr.confidence ORDER BY pr.run_date

// the vector-store knowledge chunks
MATCH (c:KnowledgeChunk) RETURN c.title, c.category
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| App shows CSV backend | Neo4j not up — `docker compose up -d`, then restart backend |
| `Neo.ClientError...password` | `NEO4J_PASSWORD` in `.env` must be ≥ 8 chars and match the container; `docker compose down -v` to reset |
| Vector search returns nothing | Run `python scripts/seed_vector_store.py` |
| OCR crash on upload | PaddleOCR 3.x runs with MKLDNN disabled + fast **mobile** models — handled in `ocr_engine.py`; warmed at startup (~20s/page on CPU) |
| OCR upload times out | First upload waits for model warm-up; the client allows 180s. Server logs show `PaddleOCR initialized` when ready |
| Answers are templated, not AI-written | Set `GEMINI_API_KEY` in `.env` and restart |

---

## Credits / data sources

Clinical rules and knowledge summaries are derived from public sources: NICE
NG97, the Alzheimer's Association clinical guidelines, FDA drug labels, ADNI,
and the MAPT/FINGER/CLARITY-AD trials. MRI examples follow the OASIS dataset
convention. For research and education only.
