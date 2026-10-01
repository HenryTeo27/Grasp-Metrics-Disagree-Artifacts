"""Small, simulator-independent IO helpers for the V4 evidence namespace."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2]
REPO = PAPER.parent
OUT = PAPER / "evidence/research_v4"
NOTES = PAPER / "notes/v4"
V3 = PAPER / "evidence/prospective_v3"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def output_path(path):
    path = Path(path).resolve()
    if not any(path.is_relative_to(base.resolve()) for base in (OUT, NOTES)):
        raise ValueError(f"Not a V4 research output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, value, *, exclusive=False):
    path = output_path(path)
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as h:
        json.dump(value, h, indent=2, allow_nan=False)
        h.write("\n")


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


def write_csv(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else []
    with output_path(path).open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True, allow_nan=False)
                          if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()}
                         for row in rows)


def yes(value):
    if str(value).lower() not in ("true", "false", "1", "0"):
        raise ValueError(f"Invalid boolean {value!r}")
    return str(value).lower() in ("true", "1")
