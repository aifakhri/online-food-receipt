# Frontend

A Streamlit multi-page app that lets users upload food receipt images and chat with an AI about their purchases.

## Structure

```
frontend/
├── Dockerfile
└── src/
    ├── app.py                  # entry point, page navigation
    ├── components/
    │   ├── chat_panel.py       # reusable chat UI component
    │   └── receipt_view.py     # receipt preview and structured display
    ├── core/
    │   └── config.py           # env-based configuration
    ├── services/
    │   └── api_client.py       # HTTP client for the backend
    ├── utils/
    │   └── formatting.py       # number/text formatting helpers
    └── views/
        ├── receipt_chat.py     # Receipt page (upload + chat)
        └── assistant.py        # All Receipts page (cross-receipt assistant)
```

---

## Pages

### Receipt (`/receipt`) — default
Upload a receipt image. The backend extracts its structured data and shows it alongside a chat panel where the user can ask questions about that specific receipt. Streamed responses are used for the chat.

### All Receipts (`/assistant`)
A cross-receipt assistant. A sidebar date picker lets the user set the "as of" date so relative queries like "last 7 days" resolve correctly. Requires no upload — queries all stored receipts via the backend assistant API.

---

## Modules

### `core/config.py`

| Variable | Default | Description |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Backend base URL (override with env var) |
| `REQUEST_TIMEOUT_SECONDS` | `180` | Total request timeout |
| `CONNECT_TIMEOUT_SECONDS` | `5` | Connection timeout |
| `ACCEPTED_TYPES` | `png, jpg, jpeg, webp, pdf` | Allowed upload MIME types |

### `services/api_client.py`

`BackendClient` wraps all backend calls using `httpx`. Instantiated once per session via `@st.cache_resource`.

| Method | Description |
|---|---|
| `upload_receipt(file_name, data, mime_type)` | `POST /receipts` — upload and extract a receipt |
| `stream_receipt_answer(receipt_id, question, history)` | `POST /receipts/{id}/chat` — streamed response |
| `get_date_range()` | `GET /receipts/date-range` — earliest and latest receipt dates |
| `ask_assistant(question, history, as_of)` | `POST /chat` — cross-receipt assistant |

`BackendError` is raised on any HTTP or network error, and caught at the UI layer to show an `st.error`.

### `components/chat_panel.py`

`chat_panel(messages, placeholder, respond, height)` — renders a scrollable message history and a chat input. Calls the `respond` callable on submit and appends the result to `messages`.

### `components/receipt_view.py`

- `render_preview(data)` — shows the raw image bytes with `st.image`
- `render_receipt(receipt)` — renders merchant name, metadata caption, summary metrics (total, item count, payment method), an items table, and a totals breakdown table. A raw JSON expander is included at the bottom.

### `utils/formatting.py`

| Function | Description |
|---|---|
| `amount_decimals(receipt)` | Returns `0` if all amounts are whole numbers, `2` otherwise |
| `fmt(value, decimals)` | Formats a float with thousands separator, or `"-"` for `None` |
| `fmt_quantity(value)` | Formats quantity dropping trailing zeros (`%g`) |
| `escape_md(text)` | Escapes `$` so Streamlit doesn't parse it as LaTeX |

---

## Running

```bash
streamlit run src/app.py
```

Environment variable:

```
BACKEND_URL=http://localhost:8000
```

## Docker

```bash
docker build -f frontend/Dockerfile -t receipt-frontend .
docker run -p 8501:8501 -e BACKEND_URL=http://backend:8000 receipt-frontend
```

Exposed port: **8501**
