# Backend

A FastAPI service that extracts structured data from food receipt images using an LLM and serves a conversational AI assistant over the stored receipts.

## Structure

```
backend/
├── Dockerfile
├── .env
├── storages/
│   ├── database/food_receipts.db   # SQLite database
│   └── uploads/                    # deduped receipt images (SHA-256 named)
└── src/
    ├── app.py                      # FastAPI app, lifespan, router registration
    ├── agents/
    │   ├── assistant.py            # cross-receipt LangChain agent
    │   ├── receipt_graph.py        # LangGraph graph (extract + chat nodes)
    │   ├── tools.py                # SQL-backed tools for the assistant
    │   └── prompts.py              # system prompt strings
    ├── api/
    │   ├── chat.py                 # POST /chat endpoint
    │   ├── receipts.py             # receipt CRUD + chat endpoints
    │   ├── schemas.py              # Pydantic request/response models
    │   └── dependencies.py         # FastAPI dependency injectors
    ├── core/
    │   └── config.py               # env-based configuration
    ├── database/
    │   ├── connection.py           # SQLite connection helpers
    │   ├── repository.py           # all SQL queries
    │   └── schema.sql              # DDL
    ├── models/
    │   └── receipt.py              # Receipt and ReceiptItem Pydantic models
    └── services/
        └── ingestion.py            # file storage, dedup, extraction orchestration
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/receipts` | Upload and extract a receipt image |
| `GET` | `/receipts/date-range` | Earliest and latest receipt dates on file |
| `POST` | `/receipts/{id}/chat` | Ask a question about a specific receipt (streaming) |
| `POST` | `/chat` | Cross-receipt assistant (non-streaming) |

### `POST /receipts`
Accepts a multipart `file` upload (PNG, JPEG, WEBP; max 20 MB). Computes a SHA-256 of the file bytes — if an identical file was already extracted, the previous result is reused and no LLM call is made. Returns `{ id, reused, receipt }`.

### `POST /receipts/{id}/chat`
Streams the LLM response token by token (`text/plain; charset=utf-8`). The receipt JSON is injected as a system message; conversation history is forwarded as-is.

### `POST /chat`
Invokes the assistant agent with optional `as_of` date override (used to resolve relative date expressions). Returns `{ answer }`.

---

## Agents

### Receipt Graph (`agents/receipt_graph.py`)

A two-node LangGraph `StateGraph` with conditional routing:

```
START → route ─► extract → END   (when images are present)
               └► chat    → END   (when receipt data is already present)
```

- **extract node**: sends image(s) as base64 data URLs to the LLM with structured output (`Receipt` model), using `reasoning={"effort": "low"}`.
- **chat node**: injects the receipt JSON as a system prompt and streams the LLM response, using `reasoning={"effort": "none"}`.

### Assistant Agent (`agents/assistant.py`)

A LangChain `create_agent` with two tools and a dynamic system prompt that stamps the current date into the prompt at inference time via `AssistantContext`.

---

## Tools (`agents/tools.py`)

Both tools query the `purchases` SQLite view (only successfully extracted receipts, latest per file hash).

### `find_purchases`
Returns a JSON list of receipts with their line items. Supports filtering by `start_date`, `end_date`, `category`, `merchant` (LIKE), and `keywords` (item name fragments matched with OR). Capped at 50 receipts.

### `summarize_spending`
Returns totals (total, tax, tip, receipt count). Optionally breaks down by `day`, `merchant`, or `category`.

---

## Database

SQLite with WAL mode and foreign keys enabled. Two tables and one view:

### `receipts`
Stores file metadata, extraction status (`processing` / `extracted` / `failed`), and all extracted receipt fields. `file_sha256` is indexed together with `status` for fast dedup lookups. `reused_from` tracks which prior record the extraction was copied from.

### `receipt_items`
Line items linked to a receipt by `receipt_id`. Ordered by `position` (as printed).

### `purchases` view
Filters to `status = 'extracted'` and dedups to the latest extraction per `file_sha256`. All agent queries run against this view.

---

## Models (`models/receipt.py`)

| Model | Fields |
|---|---|
| `Receipt` | `merchant_name`, `merchant_address`, `receipt_date` (YYYY-MM-DD), `receipt_time` (HH:MM), `receipt_number`, `items`, `subtotal`, `tax`, `tip`, `total`, `payment_method`, `category` |
| `ReceiptItem` | `name`, `quantity`, `unit_price`, `total_price` |
| `Category` | `Food`, `Food & Dining`, `Bar`, `Cafe`, `Restaurant` |

The `category` field validator normalises casing and returns `None` for unrecognised values.

---

## Configuration (`core/config.py`)

| Env var | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | LLM API key |
| `MODEL_NAME` | Yes | — | Model name (e.g. `gpt-5.4-mini`) |
| `OPENAI_BASE_URL` | No | OpenAI default | Custom inference endpoint |
| `STORAGE_ROOT` | No | `backend/storages` | Root for DB and uploads |
| `APP_TIMEZONE` | No | `Asia/Jakarta` | Timezone for date resolution |

---

## Running

```bash
uvicorn app:app --app-dir src --reload
```

Requires a `.env` file (or exported env vars) with at least `OPENAI_API_KEY` and `MODEL_NAME`.

## Docker

```bash
docker build -f backend/Dockerfile -t receipt-backend .
docker run -p 8000:8000 --env-file backend/.env receipt-backend
```

Exposed port: **8000**. Storage is written to `/app/storages` inside the container — mount a volume to persist data.
