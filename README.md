### Local RAG Knowledge Copilot

**Local-first web application** for ingesting PDF documents, indexing their content, and answering questions with citations using a Retrieval-Augmented Generation pipeline that runs on local infrastructure.

This is **not a native desktop app** (no Electron/Tauri wrapper). You run a FastAPI backend and a React web UI in the browser (`localhost`). Inference, storage, and retrieval stay on your machine; the interface is a standard web app served locally.

The project addresses a real-world problem: teams often need to consult internal manuals, contracts, policies, technical documents, or regulatory PDFs without sending sensitive information to external AI services or relying on keyword search alone.

---

## Domain Problem

Document search is not just file storage. When a user asks a question over a private document base, the system must retrieve the right evidence, preserve traceability, avoid duplicate ingestion, and make the answer auditable through citations.

This requires the system to solve challenges that do not typically exist in a traditional CRUD application:

* PDF documents must be parsed into meaningful chunks instead of stored as opaque files.
* Duplicate files must be detected deterministically before polluting the index.
* Retrieval must combine semantic similarity with lexical search to avoid missing exact terms.
* Answers must expose the source chunks used to generate the response.
* Local model execution must work without depending on hosted LLM APIs.
* Query execution needs observability for latency, retrieval quality, and citation coverage.
* User-facing flows must support upload, document discovery, and question answering without requiring curl or backend knowledge.

---

## Core Capabilities

### PDF Ingestion

Documents can be uploaded from the web UI or ingested through the API. The backend accepts PDF files, validates input paths, computes content hashes, rejects duplicates, and stores indexed metadata.

### Document Parsing and Chunking

PDF content is extracted with Docling and split into retrievable chunks. Each chunk keeps source metadata such as document ID, source file, page information, headings, version, and chunk ID.

### Hybrid Retrieval

Queries are resolved through a combination of vector search and SQLite FTS5 lexical search. Reciprocal Rank Fusion merges both result sets so exact keyword matches and semantic matches can reinforce each other.

### Reranking and Context Selection

Candidate chunks are reranked before generation. The retrieval pipeline separates candidate collection, reranking, final context selection, and answer generation.

### Local Answer Generation

Responses are generated through `llama.cpp` using a local GGUF model configured with `LLAMACPP_MODEL_PATH`. The system is designed to run without sending document content to external AI providers.

### Citation Traceability

Every answer includes citations and retrieved chunks so users can inspect the evidence behind the generated response.

### Observability

Structured logs, correlation IDs, Prometheus metrics, stage timings, and citation coverage tracking are included to make the RAG pipeline measurable instead of opaque.

### Web UI

The React interface supports PDF upload, indexed document listing, backend connectivity status, dark mode, and natural-language querying from the browser.

---

## Product Features

* PDF upload through the web interface.
* API-based ingestion from a local S3-like folder.
* Deterministic document IDs based on PDF content hash.
* Duplicate document protection with `409 Conflict` responses.
* Document library with indexed file metadata.
* Natural-language question answering over indexed PDFs.
* Retrieved chunks and source citations returned with each answer.
* Hybrid semantic and lexical retrieval.
* RRF-based result fusion.
* MMR/reranking stage for final context selection.
* Local LLM generation through `llama.cpp`.
* Prometheus-compatible `/metrics` endpoint.
* Production serving of the built UI from FastAPI.

---

## Architecture and Technology Stack

### Backend

* Python 3.12
* FastAPI
* Pydantic v2
* Docling
* ChromaDB persistent vector store
* SQLite FTS5 lexical fallback/search
* sentence-transformers MiniLM embeddings
* llama.cpp local generation
* structlog
* prometheus-client

### Frontend

* React 19
* TypeScript
* Vite
* Tailwind CSS
* Radix UI primitives
* TanStack Query
* lucide-react

### Contracts

Pydantic models define the API contracts for ingestion, querying, document listing, retrieved chunks, citations, and structured errors.

### Local Infrastructure

The service persists vector data in ChromaDB and lexical/index metadata in SQLite under `core/data/`. PDF files are read from `core/s3/` or uploaded through the browser. **These paths are gitignored** — indexes and uploaded documents are created locally at runtime and are not part of the repository.

### Quality Assurance

* Unit tests
* Integration tests
* Contract tests
* E2E evaluation utilities
* Typed API contracts
* Explicit error codes for API failures

The backend is organized around service boundaries for ingestion, retrieval, reranking, generation, stores, contracts, configuration, and observability. This keeps business logic out of route handlers and makes the RAG pipeline easier to test, replace, and tune.

---

## Main API Endpoints

* `POST /v1/upload` - upload and ingest a PDF through `multipart/form-data`.
* `POST /v1/ingest` - ingest one or more PDFs from the configured local source directory.
* `POST /v1/query` - ask a question and receive an answer with citations and retrieved chunks.
* `GET /v1/documents` - list indexed documents.
* `GET /metrics` - expose Prometheus metrics.

---

## Environment Variables

* `LLAMACPP_MODEL_PATH` - required for answer generation.
* `CHROMA_PERSIST_DIR` - ChromaDB persistence directory. Default: `./data/chroma`.
* `SQLITE_PATH` - SQLite database path. Default: `./data/rag.db`.
* `S3_DIR` - local folder used as the source for API-based PDF ingestion.
* `RAG_CANDIDATE_K` - number of initial retrieval candidates. Default: `30`.
* `RAG_RERANK_K` - number of candidates passed into reranking. Default: `10`.
* `RAG_FINAL_K` - number of chunks used as final generation context. Default: `5`.

---

## Running the Web UI

The backend must be running on `localhost:8000` for the development UI proxy to work.

```bash
cd ui
npm install
npm run dev
```

The UI is available at:

```text
http://localhost:5173
```

For production, build the UI and let FastAPI serve `ui/dist/`:

```bash
cd ui
npm run build
```

---

## Models

Answer generation requires a local GGUF model configured through `LLAMACPP_MODEL_PATH`.

If you need to download a model, use:

```bash
python core/services/download_models.py
```

---

## Project Scope

Local RAG Knowledge Copilot is a complete local-first RAG application for PDF-based knowledge bases.

The delivered scope includes PDF ingestion, duplicate detection, persistent vector indexing, lexical search, hybrid retrieval, reranking, local answer generation, citation-aware responses, observability, API contracts, automated tests, and a web interface for upload and querying.

The system is designed for local document consultation workflows where privacy, traceability, and source-backed answers matter more than generic chatbot behavior.

---

## Future Evolution

Future improvements can focus on expanding the system beyond the current local PDF knowledge-base scope:

* Better retrieval evaluation with larger golden datasets.
* More advanced ranking strategies and configurable retrieval profiles.
* Multi-user access control and document collection management.
* Expanded file format support beyond PDFs.
* Improved operational tooling for backups, model management, and deployment.
* Packaging options for simpler local installation and production rollout.
