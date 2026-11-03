from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from itertools import pairwise
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

_TOKEN = re.compile(r"\w+", re.UNICODE)
_BLOCK_ELEMENTS = 1 << 24


class _CSR:
    def __init__(
        self,
        indptr: NDArray[np.int64],
        indices: NDArray[np.int64],
        data: NDArray[np.float32],
        n_cols: int,
    ) -> None:
        self.indptr = indptr
        self.indices = indices
        self.data = data
        self.shape = (len(indptr) - 1, n_cols)
        self.block = max(1, _BLOCK_ELEMENTS // n_cols)

    def _blocks(self) -> Iterator[tuple[int, int, NDArray[np.float32]]]:
        n_rows, n_cols = self.shape
        for start in range(0, n_rows, self.block):
            stop = min(start + self.block, n_rows)
            lo, hi = self.indptr[start], self.indptr[stop]
            dense = np.zeros((stop - start, n_cols), dtype=np.float32)
            rows = np.repeat(np.arange(stop - start), np.diff(self.indptr[start : stop + 1]))
            dense[rows, self.indices[lo:hi]] = self.data[lo:hi]
            yield start, stop, dense

    def dot(self, other: NDArray[np.float32]) -> NDArray[np.float32]:
        out = np.empty((self.shape[0], other.shape[1]), dtype=np.float32)
        for start, stop, dense in self._blocks():
            out[start:stop] = dense @ other
        return out

    def tdot(self, other: NDArray[np.float32]) -> NDArray[np.float32]:
        out = np.zeros((self.shape[1], other.shape[1]), dtype=np.float32)
        for start, stop, dense in self._blocks():
            out += dense.T @ other[start:stop]
        return out


class LSAEmbedder:
    def __init__(
        self,
        dim: int = 256,
        char_ngrams: tuple[int, int] | None = (3, 5),
        word_bigrams: bool = True,
        min_df: int = 2,
        max_df: float = 0.95,
        max_features: int = 50_000,
        n_iter: int = 4,
        seed: int = 0,
    ) -> None:
        if dim <= 0 or max_features <= 0 or not 0 < max_df <= 1:
            raise ValueError("dim and max_features must be positive and max_df in (0, 1]")
        self.dim = dim
        self.char_ngrams = char_ngrams
        self.word_bigrams = word_bigrams
        self.min_df = min_df
        self.max_df = max_df
        self.max_features = max_features
        self.n_iter = n_iter
        self.seed = seed
        self.vocabulary_: dict[str, int] = {}
        self.idf_: NDArray[np.float32] | None = None
        self.projection_: NDArray[np.float32] | None = None

    @property
    def output_dim(self) -> int:
        return self._fitted_projection().shape[1]

    def _fitted_projection(self) -> NDArray[np.float32]:
        if self.projection_ is None:
            raise RuntimeError("Embedder is not fitted; call fit() or load()")
        return self.projection_

    def _features(self, text: str) -> Counter[str]:
        words = _TOKEN.findall(text.lower())
        features = Counter(f"w:{w}" for w in words)
        if self.word_bigrams:
            features.update(f"b:{a} {b}" for a, b in pairwise(words))
        if self.char_ngrams:
            low, high = self.char_ngrams
            for word in words:
                padded = f"<{word}>"
                for n in range(low, min(high, len(padded)) + 1):
                    features.update(f"c:{padded[i : i + n]}" for i in range(len(padded) - n + 1))
        return features

    def _weights(self, features: Counter[str]) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
        pairs = [(self.vocabulary_[f], c) for f, c in features.items() if f in self.vocabulary_]
        if not pairs:
            return np.empty(0, np.int64), np.empty(0)
        array = np.array(pairs, dtype=np.int64)
        idx = array[:, 0]
        weights = (1.0 + np.log(array[:, 1])) * self.idf_[idx]
        return idx, weights / np.linalg.norm(weights)

    def fit(self, texts: Iterable[str]) -> LSAEmbedder:
        docs = [self._features(text) for text in texts]
        n_docs = len(docs)
        df: Counter[str] = Counter()
        for doc in docs:
            df.update(doc.keys())
        ceiling = self.max_df * n_docs
        kept = sorted(
            ((f, c) for f, c in df.items() if self.min_df <= c <= ceiling),
            key=lambda item: (-item[1], item[0]),
        )[: self.max_features]
        if not kept:
            raise ValueError("No features survived min_df/max_df pruning; add documents or lower min_df")

        self.vocabulary_ = {feature: i for i, (feature, _) in enumerate(kept)}
        counts = np.array([c for _, c in kept], dtype=np.float64)
        self.idf_ = (np.log((1 + n_docs) / (1 + counts)) + 1.0).astype(np.float32)

        weighted = [self._weights(doc) for doc in docs]
        indptr = np.zeros(n_docs + 1, dtype=np.int64)
        np.cumsum([len(idx) for idx, _ in weighted], out=indptr[1:])
        indices = np.concatenate([idx for idx, _ in weighted])
        data = np.concatenate([w for _, w in weighted]).astype(np.float32)
        self.projection_ = self._randomized_svd(_CSR(indptr, indices, data, len(kept)))
        return self

    def _randomized_svd(self, matrix: _CSR) -> NDArray[np.float32]:
        n_docs, n_features = matrix.shape
        rank = min(self.dim, n_docs, n_features)
        width = min(rank + 10, n_docs, n_features)
        rng = np.random.default_rng(self.seed)
        omega = rng.standard_normal((n_features, width), dtype=np.float32)
        q = np.linalg.qr(matrix.dot(omega))[0]
        for _ in range(self.n_iter):
            q = np.linalg.qr(matrix.dot(np.linalg.qr(matrix.tdot(q))[0]))[0]
        _, _, vt = np.linalg.svd(matrix.tdot(q).T, full_matrices=False)
        return np.ascontiguousarray(vt[:rank].T, dtype=np.float32)

    def embed(self, texts: str | Sequence[str]) -> NDArray[np.float32]:
        projection = self._fitted_projection()
        batch = [texts] if isinstance(texts, str) else texts
        out = np.zeros((len(batch), projection.shape[1]), dtype=np.float32)
        for i, text in enumerate(batch):
            idx, weights = self._weights(self._features(text))
            if idx.size:
                out[i] = weights @ projection[idx]
        return out

    def fit_embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self.fit(texts).embed(texts)

    def save(self, path: str | os.PathLike[str]) -> None:
        projection = self._fitted_projection()
        config = {
            "dim": self.dim,
            "char_ngrams": self.char_ngrams,
            "word_bigrams": self.word_bigrams,
            "min_df": self.min_df,
            "max_df": self.max_df,
            "max_features": self.max_features,
            "n_iter": self.n_iter,
            "seed": self.seed,
        }
        vocab = np.array(sorted(self.vocabulary_, key=self.vocabulary_.__getitem__))
        with Path(path).open("wb") as fh:
            np.savez_compressed(
                fh, vocab=vocab, idf=self.idf_, projection=projection, config=np.array(json.dumps(config))
            )

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> LSAEmbedder:
        with np.load(path, allow_pickle=False) as data:
            config = json.loads(str(data["config"]))
            if config["char_ngrams"]:
                config["char_ngrams"] = tuple(config["char_ngrams"])
            embedder = cls(**config)
            embedder.vocabulary_ = {feature: i for i, feature in enumerate(data["vocab"].tolist())}
            embedder.idf_ = data["idf"]
            embedder.projection_ = data["projection"]
        return embedder
