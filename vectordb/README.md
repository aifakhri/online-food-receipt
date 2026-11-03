# vectordb

A lightweight, dependency-free in-memory vector database with a built-in LSA (Latent Semantic Analysis) embedder. No external ML frameworks required — only NumPy.

## Modules

| File | Responsibility |
|---|---|
| `embedder.py` | `LSAEmbedder` — TF-IDF + randomized SVD to produce dense float32 vectors |
| `store.py` | `VectorDB` — cosine-similarity search with metadata filtering and persistence |
| `filters.py` | `compile_filter` — MongoDB-style filter compiler for metadata predicates |

---

## Quick Start

```python
from vectordb import LSAEmbedder, VectorDB

texts = ["revenue grew 12%", "credit risk exposure rose", "branch closures reduced cost"]
metadatas = [{"division": "finance"}, {"division": "risk"}, {"division": "ops"}]

embedder = LSAEmbedder(dim=16, min_df=1)
db = VectorDB(embedder.output_dim if embedder.fit(texts) else 0)
db.upsert(embedder.embed(texts), texts, metadatas)

results = db.search(embedder.embed("loan problems"), k=2, where={"division": "risk"})
for r in results:
    print(f"{r.score:.3f}  {r.text}")
```

---

## LSAEmbedder

Fits a TF-IDF vocabulary then compresses it to `dim` dimensions via randomized SVD. Supports word unigrams, word bigrams, and character n-grams for typo tolerance.

### Constructor

```python
LSAEmbedder(
    dim=256,              # output vector size
    char_ngrams=(3, 5),   # character n-gram range; None to disable
    word_bigrams=True,    # include adjacent word pairs
    min_df=2,             # minimum document frequency
    max_df=0.95,          # maximum document frequency (fraction)
    max_features=50_000,  # vocabulary size cap
    n_iter=4,             # SVD power-iteration passes
    seed=0,
)
```

### Key Methods

| Method | Description |
|---|---|
| `fit(texts)` | Build vocabulary and projection matrix from a corpus |
| `embed(texts)` | Return `(n, dim)` float32 array; single string or list accepted |
| `fit_embed(texts)` | `fit` + `embed` in one call |
| `save(path)` | Serialize to a `.npz` file |
| `LSAEmbedder.load(path)` | Restore from `.npz` |
| `output_dim` | Actual dimension after fitting (≤ `dim`) |

---

## VectorDB

Thread-safe in-memory store. Vectors are L2-normalized on insert and compared via dot product (equivalent to cosine similarity).

### Constructor

```python
VectorDB(dim, initial_capacity=1024)
```

### Key Methods

| Method | Returns | Description |
|---|---|---|
| `upsert(vectors, texts, metadatas, ids)` | `list[str]` | Insert or update records; auto-generates UUIDs if `ids` is omitted |
| `delete(ids)` | `int` | Remove records by id; returns count removed |
| `get(ids)` | `list[Record]` | Fetch records by id without scoring |
| `search(query, k, where, score_threshold)` | `list[SearchResult]` | Top-k cosine search with optional filter |
| `save(directory)` | — | Persist to `vectors.npy` + `records.json` (atomic via temp-file swap) |
| `VectorDB.load(directory)` | `VectorDB` | Restore from a saved directory |

### Record & SearchResult

```python
@dataclass
class Record:
    id: str
    text: str
    metadata: dict

@dataclass
class SearchResult:
    id: str
    text: str
    metadata: dict
    score: float      # cosine similarity in [-1, 1]
```

---

## Metadata Filtering

Pass a `where` dict to `search()` to narrow candidates before scoring. Supports a MongoDB-style syntax.

### Operators

| Operator | Meaning |
|---|---|
| `{"key": value}` | equality (shorthand for `$eq`) |
| `{"key": {"$eq": v}}` | equal |
| `{"key": {"$ne": v}}` | not equal |
| `{"key": {"$gt/$gte/$lt/$lte": v}}` | comparison |
| `{"key": {"$in": [...]}}` | value in list |
| `{"key": {"$nin": [...]}}` | value not in list |
| `{"key": {"$exists": bool}}` | field presence |
| `{"$and": [...]}` | all sub-filters match |
| `{"$or": [...]}` | any sub-filter matches |
| `{"$not": {...}}` | negate a sub-filter |

Dot-notation traverses nested metadata: `{"parent.child": value}`.

### Examples

```python
# exact match
db.search(q, where={"division": "risk"})

# membership
db.search(q, where={"division": {"$in": ["risk", "ops"]}})

# range
db.search(q, where={"score": {"$gte": 0.5}})

# compound
db.search(q, where={"$and": [{"division": "risk"}, {"score": {"$gt": 0}}]})
```

---

## Persistence

```python
# save
embedder.save("model.npz")
db.save("db_dir/")

# load
embedder = LSAEmbedder.load("model.npz")
db = VectorDB.load("db_dir/")
```

The store writes to temp files first and renames atomically, so a crash mid-save never leaves a corrupt store.
