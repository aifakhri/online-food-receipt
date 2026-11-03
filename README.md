# Online Food Receipt

A collection of experiments and a full-stack AI application for food receipt understanding.

---

## Contents

### 1. AI Engineering Knowledge
[Engineering_Knowledge_AI_Agent_Test.md](Engineering_Knowledge_AI_Agent_Test.md)

Written answers covering REST API vs MCP in AI contexts, ensuring agent correctness, Docker in AI workflows, and LLM fine-tuning from scratch.

---

### 2. Generate Insights from Data
[insights_from_data.ipynb](insights_from_data.ipynb)

A notebook that explores and visualises patterns in the customer dataset using Pandas, Polars, and Plotly.

**Run:**
```bash
uv run --group dev jupyter notebook insights_from_data.ipynb
```
> The CSV file must exist at `customer_data/customers-100000.csv` before running.
---

[![Check the video explanation](https://drive.google.com/file/d/1aQHOhKlsWI1M4CV-JqfhBJXGul7HD-0I/view?usp=sharing)](https://drive.google.com/file/d/1aQHOhKlsWI1M4CV-JqfhBJXGul7HD-0I/view?usp=sharing)

### 3. Load Large Files
[load_large_files.py](load_large_files.py)

Benchmarks three Polars loading strategies on `customer_data/customers-2000000.csv` and prints peak RSS memory and elapsed time for each.

| Strategy | Description |
|---|---|
| `normal_load` | `pl.read_csv` — full eager load |
| `lazy_in_memory` | `pl.scan_csv` + `.collect(engine="in-memory")` |
| `lazy_streaming` | `pl.scan_csv` + `.collect(engine="streaming")` — lowest peak memory |

**Run:**
```bash
uv run --group dev python load_large_files.py normal_load
uv run --group dev python load_large_files.py lazy_in_memory
uv run --group dev python load_large_files.py lazy_streaming
```

> The CSV file must exist at `customer_data/customers-2000000.csv` before running.
---

[![Check the video explanation](https://drive.google.com/file/d/1AF7R0C-bNTcy7v6XDSJqX1eNNEM3P8Jd/view?usp=sharing)](https://drive.google.com/file/d/1AF7R0C-bNTcy7v6XDSJqX1eNNEM3P8Jd/view?usp=sharing)

### 4. VectorDB
[vectordb/README.md](vectordb/README.md)

A lightweight in-memory vector database with a built-in LSA embedder — no ML frameworks required, only NumPy. Covers `LSAEmbedder`, `VectorDB`, metadata filtering, and persistence.

To check how it works use:
**Run:**
```bash
uv run --group dev jupyter notebook test_vector_db.ipynb
```
---

[![Check the video explanation](https://drive.google.com/file/d/11A-ueeNMyVxq7WRvl17DBiKns1_3IgaT/view?usp=sharing)](https://drive.google.com/file/d/11A-ueeNMyVxq7WRvl17DBiKns1_3IgaT/view?usp=sharing)

### 5. Chat UI
A two-service application: a FastAPI backend that extracts receipt data with an LLM and a Streamlit frontend for uploading receipts and chatting about them.

**Dataset baseline:** The receipts used for testing this UI come from the [Voxel51 Consolidated Receipt Dataset](https://huggingface.co/datasets/Voxel51/consolidated_receipt_dataset) on Hugging Face. Note that the restaurant receipts in this dataset are **not sequential** — they are not ordered by date and do not represent purchases made across continuous days. As a result, multi-day queries such as *"What did I spend last week?"* or *"Show me all meals from the past 3 days"* will not return meaningful answers, since the receipt dates are not tied to any real or consistent timeline.

- Backend details → [backend/BACKEND.md](backend/BACKEND.md)
- Frontend details → [frontend/FRONTEND.md](frontend/FRONTEND.md)

#### Setting up `.env`

The backend requires API credentials that are **not included in the repository**. Create a `.env` file at the **project root** (same level as `docker-compose.yaml`) before running:

```bash
# .env
OPENAI_API_KEY=your-api-key-here
MODEL_NAME=gpt-6-luna           # default model; can be replaced with any compatible model name

# Optional
OPENAI_BASE_URL=https://api.openai.com/v1   # override for custom endpoints
APP_TIMEZONE=Asia/Jakarta                    # default: Asia/Jakarta
```

> `STORAGE_ROOT` is set automatically by `docker-compose.yaml` and does not need to be in `.env`.

[![Check the video explanation](https://drive.google.com/file/d/1CxV00lAd7flTWnNV1-u18xM0oaLXPcyV/view?usp=sharing)](https://drive.google.com/file/d/1CxV00lAd7flTWnNV1-u18xM0oaLXPcyV/view?usp=sharing)

#### Run with Docker Compose

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend (Streamlit) | http://localhost:8501 |
| Backend (FastAPI) | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

Receipt images and the SQLite database are persisted to `backend/storages/` on the host via a volume mount.
