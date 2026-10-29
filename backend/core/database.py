"""
Minimal JSON-file data store standing in for MongoDB/PostgreSQL in the
prototype, as described on the Technology Stack slide. Each collection is
one JSON file holding a list of records. Reads/writes are guarded by a
lock so concurrent requests in the dev server don't corrupt a file.
"""
import json
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_locks: dict[str, threading.Lock] = {}


def _lock_for(name: str) -> threading.Lock:
    if name not in _locks:
        _locks[name] = threading.Lock()
    return _locks[name]


def _path_for(collection: str) -> Path:
    return DATA_DIR / f"{collection}.json"


def read_all(collection: str) -> list[dict[str, Any]]:
    path = _path_for(collection)
    if not path.exists():
        return []
    with _lock_for(collection):
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)


def write_all(collection: str, records: list[dict[str, Any]]) -> None:
    path = _path_for(collection)
    with _lock_for(collection):
        with path.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)


def insert(collection: str, record: dict[str, Any]) -> dict[str, Any]:
    records = read_all(collection)
    records.append(record)
    write_all(collection, records)
    return record


def find_one(collection: str, **filters: Any) -> dict[str, Any] | None:
    for record in read_all(collection):
        if all(record.get(key) == value for key, value in filters.items()):
            return record
    return None


def update_one(collection: str, match_id: str, id_field: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    records = read_all(collection)
    updated = None
    for record in records:
        if record.get(id_field) == match_id:
            record.update(patch)
            updated = record
            break
    if updated is not None:
        write_all(collection, records)
    return updated


def next_id(collection: str, id_field: str, prefix: str) -> str:
    records = read_all(collection)
    existing = [r[id_field] for r in records if id_field in r]
    n = 1
    while f"{prefix}{n:04d}" in existing:
        n += 1
    return f"{prefix}{n:04d}"
