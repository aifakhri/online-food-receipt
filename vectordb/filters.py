from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

Metadata = Mapping[str, Any]
Filter = Mapping[str, Any]
Predicate = Callable[[Metadata], bool]

_MISSING = object()


def _resolve(metadata: Metadata, key: str) -> Any:
    value: Any = metadata
    for part in key.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _guarded(fn: Callable[[Any, Any], bool]) -> Callable[[Any, Any], bool]:
    def wrapped(value: Any, target: Any) -> bool:
        if value is _MISSING:
            return False
        try:
            return bool(fn(value, target))
        except TypeError:
            return False

    return wrapped


def _eq(value: Any, target: Any) -> bool:
    if isinstance(value, list) and not isinstance(target, list):
        return target in value
    return value == target


def _in(value: Any, target: Any) -> bool:
    if isinstance(value, list):
        return any(item in target for item in value)
    return value in target


_FIELD_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "$eq": _guarded(_eq),
    "$ne": lambda v, t: v is _MISSING or not _eq(v, t),
    "$gt": _guarded(lambda v, t: v > t),
    "$gte": _guarded(lambda v, t: v >= t),
    "$lt": _guarded(lambda v, t: v < t),
    "$lte": _guarded(lambda v, t: v <= t),
    "$in": _guarded(_in),
    "$nin": lambda v, t: v is _MISSING or not _in(v, t),
    "$exists": lambda v, t: (v is not _MISSING) is bool(t),
}


def _always(_: Metadata) -> bool:
    return True


def compile_filter(spec: Filter | None) -> Predicate:
    if not spec:
        return _always
    predicates = [_compile_clause(key, value) for key, value in spec.items()]
    if len(predicates) == 1:
        return predicates[0]
    return lambda metadata: all(p(metadata) for p in predicates)


def _compile_clause(key: str, value: Any) -> Predicate:
    match key:
        case "$and":
            subs = [compile_filter(s) for s in value]
            return lambda metadata: all(p(metadata) for p in subs)
        case "$or":
            subs = [compile_filter(s) for s in value]
            return lambda metadata: any(p(metadata) for p in subs)
        case "$not":
            sub = compile_filter(value)
            return lambda metadata: not sub(metadata)
        case _ if key.startswith("$"):
            raise ValueError(f"Unsupported logical operator: {key}")

    if isinstance(value, Mapping) and value and all(k.startswith("$") for k in value):
        checks: list[tuple[Callable[[Any, Any], bool], Any]] = []
        for op, target in value.items():
            if op not in _FIELD_OPS:
                raise ValueError(f"Unsupported field operator: {op}")
            if op in {"$in", "$nin"} and not isinstance(target, (list, tuple, set, frozenset)):
                raise ValueError(f"{op} expects a list, got {type(target).__name__}")
            checks.append((_FIELD_OPS[op], target))
    else:
        checks = [(_FIELD_OPS["$eq"], value)]

    def predicate(metadata: Metadata) -> bool:
        resolved = _resolve(metadata, key)
        return all(fn(resolved, target) for fn, target in checks)

    return predicate
