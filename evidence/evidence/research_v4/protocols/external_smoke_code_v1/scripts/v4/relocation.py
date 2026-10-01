"""Explicit receipts for user-authorized retirement, without changing old locks."""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

from .common import OUT, read_csv, read_json, sha256, utc_now, write_json

ARCHIVE = Path("F:/project/Dexterous-Hand-Control-Sim-history-20261001")
RECEIPT = "manifests/authorized_cleanup.json"


def verify_entry(entry, expected):
    if entry["sha256"] != expected["sha256"] or entry["bytes"] != expected["bytes"]:
        raise ValueError("Relocation does not match original protection manifest")
    with zipfile.ZipFile(entry["archive"]) as archive:
        info = archive.getinfo(entry["entry"])
        if info.file_size != expected["bytes"]:
            raise ValueError("Archived entry size changed")
        with archive.open(info) as stream:
            h = hashlib.file_digest(stream, "sha256").hexdigest()
    if h != expected["sha256"]:
        raise ValueError("Archived entry hash changed")


def record_cleanup():
    protected = read_json(OUT / "manifests/historical_hashes.json")
    receipts_path = ARCHIVE / "receipts.json"
    receipts = read_json(receipts_path)
    if isinstance(receipts, dict):
        receipts = [receipts]
    groups = {r["Group"]: r for r in receipts}
    group = groups["merged-paper-retired-releases"]
    for path, key in ((group["Archive"], "ArchiveSHA256"),
                      (group["Manifest"], "ManifestSHA256")):
        if sha256(path) != group[key]:
            raise ValueError(f"Cleanup receipt hash mismatch: {path}")
    files = {}
    for row in read_csv(group["Manifest"]):
        prefix = "merged-hl-grasping-paper/"
        if not row["Path"].startswith(prefix):
            raise ValueError("Unexpected relocation outside merged paper")
        rel = row["Path"][len(prefix):]
        if not rel.startswith("dist/") or rel not in protected["files"]:
            raise ValueError(f"Unexpected retired release: {rel}")
        entry = dict(sha256=row["SHA256"], bytes=int(row["Bytes"]),
                     archive=group["Archive"], entry=row["Path"])
        verify_entry(entry, protected["files"][rel])
        files[rel] = entry
    payload = dict(created_utc=utc_now(), authorization_date="2026-10-01",
                   authorization="User requested removal of merged V1/V2 and retired pre-merge material; reusable material may be archived on F:/project.",
                   original_protection_manifest_sha256=sha256(OUT / "manifests/historical_hashes.json"),
                   archive_receipts=str(receipts_path), archive_receipts_sha256=sha256(receipts_path),
                   files=files, group_receipts=receipts,
                   scope="Archive-verified relocation, not preservation at original paths")
    write_json(OUT / RECEIPT, payload, exclusive=True)
    return dict(archived_protected_files=len(files), archive_groups=len(receipts))


if __name__ == "__main__":
    print(record_cleanup())
