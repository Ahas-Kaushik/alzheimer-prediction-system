<div align="center">

# 🧠 NeuroScan AI

### Agent-Based Alzheimer's Stage Prediction with a Knowledge Graph & GraphRAG

Predicts a patient's Alzheimer's stage — **Normal · MCI · AD** — by fusing a brain
**MRI**, a GAN-synthesised **PET** image, an interactive **cognitive test**, and
**blood-report** data, then stores everything in a **Neo4j knowledge graph** and
explains the results with **GraphRAG** (vector retrieval + Google Gemini).

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Neo4j](https://img.shields.io/badge/Neo4j-5-008CC1?logo=neo4j&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-orchestration-1C3C3C)
![Gemini](https://img.shields.io/badge/Gemini-RAG-8E75B2?logo=googlegemini&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-ML-EE4C2C?logo=pytorch&logoColor=white)

<em>⚕️ Educational / research project (BMSCE, 6th sem AIML). Outputs are decision support — <strong>not</strong> a medical diagnosis.</em>

</div>

---

## 📑 Table of contents

- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🧰 Tech stack](#-tech-stack)
- [🚀 Quick start](#-quick-start)
- [🔀 Storage routing](#-storage-routing)
- [🤖 GraphRAG API](#-graphrag-api)
- [🗂️ Project layout](#️-project-layout)
- [🔎 Inspecting the graph](#-inspecting-the-knowledge-graph)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [📚 Credits](#-credits--data-sources)

---

## ✨ Features

- 🧲 **MRI → synthetic PET** via a GAN, with a Grad-CAM attention heatmap.
- 🧪 **Interactive cognitive test** (reaction-time + gaze) feeding a composite index.
- 🩸 **Blood-report OCR** (PaddleOCR) → auto-extracts 20+ clinical fields, negation-aware.
- 🧬 **Stage classifier** (Normal / MCI / AD) fusing image, clinical and cognitive features.
- 🕸️ **Neo4j knowledge graph** stores every patient, visit, scan, prediction and twin.
- 🔍 **Vector storage inside Neo4j** (native vector index) for semantic retrieval.
- 💬 **GraphRAG "Ask AI"** — questions grounded in graph facts + retrieved guidelines,
  answered by **Gemini** (or a templated fallback with no API key).
- 🧠 **Digital brain twin** with longitudinal decline tracking.
- 💊 **Evidence-based medication** recommendations from a clinical rule engine.

---

## 🏗️ Architecture

**GraphRAG + LangGraph**, with the **vector store living inside Neo4j** (native
vector index) — so the knowledge graph *and* the vector storage are one system,
satisfying both the "knowledge graph" and "vector storage" requirements without a
second database.

```
                   ┌──────────────────────── FRONTEND (React + Vite) ───────────────────────┐
                   │  Dashboard · Patients · Scan Upload · MRI→PET · Blood Reports ·         │
                   │  Cognitive Test · Prediction · Digital Twin · Ask AI (GraphRAG panel)    │
                   └───────────────────────────────┬────────────────────────────────────────┘
                                                   │ REST (axios)
                   ┌───────────────────────────────▼────────────────────────────────────────┐
                   │                      BACKEND (FastAPI)                                   │
                   │   LangGraph pipeline:  validate ─▶ predict ─▶ reason(RAG) ─▶ END         │
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

---

## 🧰 Tech stack

| Concern | Technology |
|---|---|
| Storage / knowledge graph | **Neo4j 5** (Docker), auto-fallback to CSV |
| Vector storage | **Neo4j native vector index** (`clinical_chunks`, 384-dim, cosine) |
| Embeddings | **sentence-transformers** `all-MiniLM-L6-v2` (local, no key) |
| Orchestration | **LangGraph** `StateGraph` (validate → predict → reason) |
| RAG answers | **Google Gemini** (`gemini-flash-latest`) with templated fallback |
| ML | PyTorch — GAN (MRI→PET), ResNet features, MLP classifier, Grad-CAM |
| OCR | PaddleOCR (mobile models) + regex clinical parser |
| API / UI | FastAPI · React + Vite + Tailwind |

---

## 🚀 Quick start

> **Prerequisites:** Python 3.11 · Node 18+ · Docker Desktop · ~2 GB free disk.

### 1️⃣ Start the Neo4j knowledge graph

```bash
# from the project root (where docker-compose.yml lives)
docker compose up -d          # wait ~20-30s until healthy
```

- Browser UI → <http://localhost:7474>  (login `neo4j` / `NEO4J_PASSWORD` from `.env`)
- Bolt (app) → `bolt://localhost:7687`

> First run: `cp .env.example .env` and set `NEO4J_PASSWORD` (min 8 chars).

### 2️⃣ Backend

```bash
python -m venv .venv && .venv\Scripts\activate       # Windows
pip install -r backend/requirements.txt

python scripts/migrate_csv_to_neo4j.py               # CSV → graph (idempotent)
python scripts/seed_vector_store.py                  # embed knowledge base

uvicorn backend.main:app --reload --port 8000        # API → :8000/docs
```

### 3️⃣ Frontend

```bash
cd frontend && npm install && npm run dev            # → http://localhost:5173
```

### 4️⃣ (Optional) Enable Gemini

Get a free key at <https://aistudio.google.com/app/apikey>, add it to `.env`, and
restart the backend:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-flash-latest
```

Without a key the RAG layer returns solid **templated** answers — fully functional offline.

---

## 🔀 Storage routing

`backend/knowledge_graph/patient_store.py` selects a backend once per process:

1. `GRAPH_BACKEND=neo4j` **and** Neo4j reachable → **Neo4j knowledge graph** ✅
2. Neo4j down **and** `ALLOW_CSV_FALLBACK=True` → **CSV store** (`data/csv_db/*.csv`)
3. `GRAPH_BACKEND=csv` or `USE_CSV_FALLBACK=True` → **CSV** directly

So the app never crashes just because Docker wasn't started.

---

## 🤖 GraphRAG API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET`  | `/api/rag/status` | Active backend, vector-index state, LLM provider |
| `POST` | `/api/rag/seed` | (Re)embed the clinical knowledge base |
| `POST` | `/api/rag/ask` | `{patient_id, question}` → grounded answer + sources |
| `GET`  | `/api/rag/explain/{patient_id}` | Explain the patient's latest predicted stage |

```bash
curl -X POST http://localhost:8000/api/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"PAT-D6CBDC3C","question":"Why is this patient MCI and what should we monitor?"}'
```

Answers are grounded in (a) the patient's **graph facts** (stage, cognitive index,
blood data) and (b) the **top-k retrieved** clinical knowledge chunks. In the UI,
open a patient and use the **"Ask AI about this patient"** panel at the bottom of
the profile — it shows the answer, the provider (Gemini vs templated) and the sources.

---

## 🗂️ Project layout

```
alzheimer-prediction-system/
├── docker-compose.yml            # Neo4j 5 + APOC + vector index
├── .env.example                  # config template (copy to .env)
├── scripts/
│   ├── migrate_csv_to_neo4j.py   # CSV → knowledge graph migration
│   └── seed_vector_store.py      # embed knowledge base into vector index
├── synthetic_blood_reports/      # OCR test fixtures (see its README)
├── backend/
│   ├── main.py                   # FastAPI app + routers + startup warmup
│   ├── config.py                 # settings (Neo4j / RAG / Gemini)
│   ├── agents/
│   │   ├── agent1..4_*.py        # data proc, PET synth, cognitive, orchestrator
│   │   └── graph_pipeline.py     # LangGraph StateGraph orchestration
│   ├── knowledge_graph/
│   │   ├── neo4j_store.py         # graph CRUD (mirrors csv_fallback API)
│   │   ├── csv_fallback.py        # CSV dev store (fallback)
│   │   ├── patient_store.py       # backend router (neo4j ⇄ csv)
│   │   └── medication_mapper.py   # evidence-based medication rules
│   ├── rag/
│   │   ├── embeddings.py          # sentence-transformers wrapper
│   │   ├── knowledge_base.py      # curated clinical knowledge chunks
│   │   ├── vector_store.py        # Neo4j native vector index
│   │   └── graph_rag.py           # retrieve + ground + generate
│   ├── llm/gemini_client.py       # Gemini with templated fallback
│   ├── models/                    # GAN, classifier, OCR, report generator
│   └── api/routes/                # patients, scans, predictions, cognitive, twin, reports, rag
└── frontend/                      # React + Vite UI
```

---

## 🔎 Inspecting the knowledge graph

Open <http://localhost:7474> and run:

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

## 🛠️ Troubleshooting

| Symptom | Fix |
|---|---|
| App shows CSV backend | Neo4j not up — `docker compose up -d`, then restart backend |
| `Neo.ClientError…password` | `NEO4J_PASSWORD` must be ≥ 8 chars & match the container; `docker compose down -v` to reset |
| Vector search returns nothing | Run `python scripts/seed_vector_store.py` |
| OCR upload times out | First upload waits for model warm-up (~20s); client allows 180s. Logs show `PaddleOCR initialized` when ready |
| Answers are templated, not AI-written | Set `GEMINI_API_KEY` in `.env` and restart; if you get HTTP 429, that model's free quota is exhausted — try `gemini-flash-latest` |

---

## 📚 Credits / data sources

Clinical rules and knowledge summaries are derived from public sources: **NICE
NG97**, the **Alzheimer's Association** guidelines, **FDA** drug labels, **ADNI**,
and the **MAPT / FINGER / CLARITY-AD** trials. MRI examples follow the **OASIS**
dataset convention. For research and education only.
