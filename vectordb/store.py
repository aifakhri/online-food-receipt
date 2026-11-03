from __future__ import annotations

import json
import os
import threading
import uuid
from collections import defaultdict
from collections.abc import Hashable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .filters import Filter, compile_filter

_VECTORS_FILE = "vectors.npy"
_RECORDS_FILE = "records.json"
_GATHER_RATIO = 0.25


@dataclass(slots=True, frozen=True)
class Record:
    id: str
    text: str
    metadata: dict[str, Any]


@dataclass(slots=True, frozen=True)
class SearchResult:
    id: str
    text: str
    metadata: dict[str, Any]
    score: float


def _is_hashable(value: Any) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _indexable(metadata: Mapping[str, Any]) -> Iterator[tuple[str, Hashable]]:
    for key, value in metadata.items():
        for item in value if isinstance(value, list) else (value,):
            if _is_hashable(item):
                yield key, item


def _indexed_clause(key: str, value: Any) -> list[Hashable] | None:
    if key.startswith("$") or "." in key:
        return None
    if isinstance(value, Mapping):
        if len(value) != 1:
            return None
        ((op, target),) = value.items()
        if op == "$eq":
            value = target
        elif op == "$in" and isinstance(target, (list, tuple, set, frozenset)):
            return list(target) if all(_is_hashable(t) and not isinstance(t, list) for t in target) else None
        else:
            return None
    if isinstance(value, (list, Mapping)) or not _is_hashable(value):
        return None
    return [value]


class VectorDB:
    def __init__(self, dim: int, initial_capacity: int = 1024) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self._vectors: NDArray[np.float32] = np.empty((max(initial_capacity, 1), dim), np.float32)
        self._size = 0
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._index: dict[str, int] = {}
        self._postings: defaultdict[str, defaultdict[Hashable, set[int]]] = defaultdict(lambda: defaultdict(set))
        self._lock = threading.RLock()

    def __len__(self) -> int:
        return self._size

    def __contains__(self, record_id: object) -> bool:
        return record_id in self._index

    def _normalize(self, vectors: ArrayLike) -> NDArray[np.float32]:
        array = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if array.ndim != 2 or array.shape[1] != self.dim:
            raise ValueError(f"Expected vectors of dimension {self.dim}, got shape {array.shape}")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        if not np.all(np.isfinite(norms)) or np.any(norms == 0):
            raise ValueError("Vectors must be finite and non-zero for cosine similarity")
        return array / norms

    def _reserve(self, extra: int) -> None:
        required = self._size + extra
        if required <= len(self._vectors):
            return
        grown = np.empty((max(required, len(self._vectors) * 2), self.dim), np.float32)
        grown[: self._size] = self._vectors[: self._size]
        self._vectors = grown

    def _post(self, position: int, metadata: Mapping[str, Any]) -> None:
        for key, item in _indexable(metadata):
            self._postings[key][item].add(position)

    def _unpost(self, position: int, metadata: Mapping[str, Any]) -> None:
        for key, item in _indexable(metadata):
            values = self._postings[key]
            values[item].discard(position)
            if not values[item]:
                del values[item]

    def upsert(
        self,
        vectors: ArrayLike,
        texts: Iterable[str],
        metadatas: Iterable[dict[str, Any] | None] | None = None,
        ids: Iterable[str | None] | None = None,
    ) -> list[str]:
        normalized = self._normalize(vectors)
        count = len(normalized)
        text_list = list(texts)
        meta_list = [dict(m or {}) for m in metadatas] if metadatas is not None else [{} for _ in range(count)]
        id_list = [i or uuid.uuid4().hex for i in ids] if ids is not None else [uuid.uuid4().hex for _ in range(count)]

        if not len(text_list) == len(meta_list) == len(id_list) == count:
            raise ValueError("vectors, texts, metadatas and ids must have the same length")
        if len(set(id_list)) != count:
            raise ValueError("Duplicate ids in the same batch")

        with self._lock:
            self._reserve(sum(i not in self._index for i in id_list))
            positions = np.empty(count, dtype=np.intp)
            for n, (record_id, text, metadata) in enumerate(zip(id_list, text_list, meta_list, strict=True)):
                position = self._index.get(record_id)
                if position is None:
                    position = self._size
                    self._index[record_id] = position
                    self._ids.append(record_id)
                    self._texts.append(text)
                    self._metadatas.append(metadata)
                    self._size += 1
                else:
                    self._unpost(position, self._metadatas[position])
                    self._texts[position] = text
                    self._metadatas[position] = metadata
                self._post(position, metadata)
                positions[n] = position
            self._vectors[positions] = normalized
        return id_list

    def delete(self, ids: Iterable[str]) -> int:
        removed = 0
        with self._lock:
            for record_id in ids:
                position = self._index.pop(record_id, None)
                if position is None:
                    continue
                last = self._size - 1
                self._unpost(position, self._metadatas[position])
                if position != last:
                    moved_id = self._ids[last]
                    self._unpost(last, self._metadatas[last])
                    self._vectors[position] = self._vectors[last]
                    self._ids[position] = moved_id
                    self._texts[position] = self._texts[last]
                    self._metadatas[position] = self._metadatas[last]
                    self._index[moved_id] = position
                    self._post(position, self._metadatas[position])
                self._ids.pop()
                self._texts.pop()
                self._metadatas.pop()
                self._size = last
                removed += 1
        return removed

    def get(self, ids: Sequence[str]) -> list[Record]:
        with self._lock:
            return [
                Record(record_id, self._texts[p], dict(self._metadatas[p]))
                for record_id in ids
                if (p := self._index.get(record_id)) is not None
            ]

    def _candidates(self, where: Filter | None) -> NDArray[np.intp] | None:
        if not where:
            return None

        narrowed: set[int] | None = None
        residual: dict[str, Any] = {}
        for key, value in where.items():
            targets = _indexed_clause(key, value)
            if targets is None:
                residual[key] = value
                continue
            postings = self._postings.get(key, {})
            matched = set().union(*(postings.get(t, ()) for t in targets))
            narrowed = matched if narrowed is None else narrowed & matched
            if not narrowed:
                return np.empty(0, dtype=np.intp)

        if residual:
            predicate = compile_filter(residual)
            pool = sorted(narrowed) if narrowed is not None else range(self._size)
            return np.fromiter((i for i in pool if predicate(self._metadatas[i])), dtype=np.intp)
        return np.sort(np.fromiter(narrowed, dtype=np.intp, count=len(narrowed)))

    @staticmethod
    def _top_k(scores: NDArray[np.float32], k: int) -> NDArray[np.intp]:
        if k >= len(scores):
            return np.argsort(-scores, kind="stable")
        partition = np.argpartition(-scores, k - 1)[:k]
        return partition[np.argsort(-scores[partition], kind="stable")]

    def search(
        self,
        query: ArrayLike,
        k: int = 4,
        where: Filter | None = None,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        vector = self._normalize(query)[0]
        if k <= 0:
            return []
        with self._lock:
            if self._size == 0:
                return []
            candidates = self._candidates(where)
            if candidates is None:
                positions = np.arange(self._size)
                scores = self._vectors[: self._size] @ vector
            elif candidates.size == 0:
                return []
            else:
                positions = candidates
                if candidates.size > self._size * _GATHER_RATIO:
                    scores = (self._vectors[: self._size] @ vector)[candidates]
                else:
                    scores = self._vectors[candidates] @ vector

            results: list[SearchResult] = []
            for i in self._top_k(scores, k):
                score = float(scores[i])
                if score_threshold is not None and score < score_threshold:
                    break
                p = int(positions[i])
                results.append(SearchResult(self._ids[p], self._texts[p], dict(self._metadatas[p]), score))
            return results

    def save(self, directory: str | os.PathLike[str]) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = {
                "dim": self.dim,
                "ids": self._ids,
                "texts": self._texts,
                "metadatas": self._metadatas,
            }
            vectors_tmp = path / f"{_VECTORS_FILE}.tmp"
            records_tmp = path / f"{_RECORDS_FILE}.tmp"
            with vectors_tmp.open("wb") as fh:
                np.save(fh, self._vectors[: self._size])
            records_tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(vectors_tmp, path / _VECTORS_FILE)
            os.replace(records_tmp, path / _RECORDS_FILE)

    @classmethod
    def load(cls, directory: str | os.PathLike[str]) -> VectorDB:
        path = Path(directory)
        payload = json.loads((path / _RECORDS_FILE).read_text(encoding="utf-8"))
        vectors = np.load(path / _VECTORS_FILE)
        size = len(payload["ids"])
        if vectors.shape != (size, payload["dim"]):
            raise ValueError("Corrupted store: vectors and records are out of sync")
        db = cls(payload["dim"], initial_capacity=max(size, 1024))
        db._vectors[:size] = vectors
        db._size = size
        db._ids = payload["ids"]
        db._texts = payload["texts"]
        db._metadatas = payload["metadatas"]
        db._index = {record_id: i for i, record_id in enumerate(db._ids)}
        for position, metadata in enumerate(db._metadatas):
            db._post(position, metadata)
        return db
