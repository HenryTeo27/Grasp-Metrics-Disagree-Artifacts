"""Snapshot exact research code before a new instrumentation revision."""
from __future__ import annotations

import shutil

from .common import OUT, PAPER, output_path, read_json, sha256, utc_now, write_json


def archive_retrospective_code():
    lock = read_json(OUT / "retrospective/replay_lock.json")
    sources = PAPER / "scripts/v4"
    for rel, key in (("contact_observer.py", "observer_code_sha256"), ("adapters/allegro.py", "adapter_code_sha256")):
        if sha256(sources / rel) != lock[key]:
            raise RuntimeError(f"Source no longer matches the completed replay: {rel}")
    dest = OUT / "protocols/retrospective_code_v1"
    manifest = dest / "manifest.json"
    if manifest.exists():
        saved = read_json(manifest)
        if any(sha256(dest / p) != h for p, h in saved["files"].items()):
            raise RuntimeError("Archived source changed")
        return saved
    hashes = {}
    for path in sorted(sources.rglob("*.py")):
        rel = path.relative_to(sources)
        target = output_path(dest / "scripts/v4" / rel)
        shutil.copy2(path, target)
        hashes[target.relative_to(dest).as_posix()] = sha256(target)
    saved = dict(created_utc=utc_now(), role="Exact V4 code at completion of 177 retrospective replays",
                 files=hashes, original_v3_code="See prospective_v3/frozen_inputs and its protocol")
    write_json(manifest, saved, exclusive=True)
    return saved
