"""P0 protection, frozen-input checks, and independent historical CSV recount."""
from __future__ import annotations

from collections import defaultdict
import platform
import sys

from .common import OUT, PAPER, REPO, V3, fingerprint, read_csv, read_json, sha256
from .common import utc_now, write_csv, write_json, yes
from .relocation import RECEIPT, verify_entry


def protected_paths():
    # Explicit historical subtrees only; never traverse the CAD repository.
    for name in ("paper", "scripts", "notes", "evidence", "dist"):
        for path in (PAPER / name).rglob("*"):
            rel = path.relative_to(PAPER)
            if not path.is_file() or "__pycache__" in rel.parts:
                continue
            if any(part in {"research_v4", "v4", "deps"} for part in rel.parts):
                continue
            if name == "dist" and "_v4" in path.name:
                continue
            yield path
    for name in ("README.md", "requirements-simulation.txt", "requirements-paper.txt"):
        path = PAPER / name
        if path.exists():
            yield path


def protect():
    dest = OUT / "manifests/historical_hashes.json"
    if dest.exists():
        return verify_protection()
    files = {p.relative_to(PAPER).as_posix(): dict(sha256=sha256(p), bytes=p.stat().st_size)
             for p in sorted(set(protected_paths()))}
    payload = dict(created_utc=utc_now(), scope="Historical merged-paper trees; installed deps excluded",
                   files=files, file_count=len(files), total_bytes=sum(x["bytes"] for x in files.values()))
    write_json(dest, payload, exclusive=True)
    return dict(protection="CREATED", file_count=len(files), total_bytes=payload["total_bytes"])


def verify_protection():
    manifest = read_json(OUT / "manifests/historical_hashes.json")
    relocated = {}
    if (OUT / RECEIPT).exists():
        receipt = read_json(OUT / RECEIPT)
        if receipt["original_protection_manifest_sha256"] != sha256(OUT / "manifests/historical_hashes.json"):
            raise RuntimeError("Original protection manifest changed after relocation")
        relocated = receipt["files"]
    missing, changed, archived, archive_errors = [], [], [], []
    for rel, value in manifest["files"].items():
        path = PAPER / rel
        if not path.exists():
            if rel in relocated:
                try:
                    verify_entry(relocated[rel], value)
                    archived.append(rel)
                except (OSError, ValueError, KeyError, RuntimeError) as exc:
                    archive_errors.append(dict(path=rel, error=str(exc)))
            else:
                missing.append(rel)
        elif sha256(path) != value["sha256"]:
            changed.append(rel)
    ok = not (missing or changed or archive_errors)
    result = dict(protection=("PASS_WITH_AUTHORIZED_RELOCATION" if archived else "PASS") if ok else "FAIL",
                  file_count=len(manifest["files"]), missing=missing, changed=changed,
                  authorized_archived_files=archived, archive_errors=archive_errors)
    if not ok:
        raise RuntimeError(result)
    return result


def frozen_inputs():
    protocol = read_json(V3 / "protocol.json")
    lock = read_json(V3 / "suite_lock.json")
    archive_bad = [p for p, h in protocol["files"].items() if sha256(V3 / "frozen_inputs" / p) != h]
    current_bad = [p for p, h in protocol["files"].items()
                   if not (REPO / p).exists() or sha256(REPO / p) != h]
    metadata_bad = [p for p, h in lock["hashes"].items() if sha256(V3 / p) != h]
    return dict(frozen_input_count=len(protocol["files"]), archive_mismatches=archive_bad,
                current_v3_input_mismatches=current_bad, suite_mismatches=metadata_bad,
                historical_other_runtime_locks="Previously disclosed failures are not altered")


def recount():
    rows = read_csv(V3 / "case_results.csv")
    fresh = [r for r in rows if r["block"].startswith("new") and r["k"] == "6"]
    fields = ("legacy_success", "contiguous_success", "clear_contiguous_success")
    counts = {p: {f: sum(yes(r[f]) for r in fresh if r["policy"] == p) for f in fields}
              for p in ("baseline", "repair", "no_extra")}
    a = {r["case_id"]: r for r in fresh if r["policy"] == "baseline"}
    b = {r["case_id"]: r for r in fresh if r["policy"] == "repair"}
    assert a.keys() == b.keys() and len(a) == 360
    excluded = {p: {r["case_id"] for r in fresh if r["policy"] == p and
                   yes(r["contiguous_success"]) and not yes(r["clear_contiguous_success"])}
                for p in ("baseline", "repair")}
    gains = [key for key in a if not yes(a[key][fields[2]]) and yes(b[key][fields[2]])]
    losses = [key for key in a if yes(a[key][fields[2]]) and not yes(b[key][fields[2]])]
    assert counts["baseline"][fields[2]] == 37 and counts["repair"][fields[2]] == 48
    assert len(gains) == 11 and not losses
    assert all(a[key]["family"] == "sphere_random" for key in gains)
    assert all(len(v) == 85 for v in excluded.values())
    result = dict(level="CSV recount, not dynamic replay", fresh_scenes=360, counts=counts,
                  gains=gains, losses=losses,
                  exclusions={p: len(v) for p, v in excluded.items()},
                  exclusion_intersection=len(excluded["baseline"] & excluded["repair"]),
                  exclusion_union=len(excluded["baseline"] | excluded["repair"]),
                  selected_equals_coverage=all(r[f] == r["selected_" + f] for r in rows for f in fields))
    write_json(OUT / "reports/historical_recount.json", result)
    return result


def candidate_registry():
    jobs = {j["job_id"]: j for j in read_json(V3 / "jobs.json")}
    members = [m for m in read_json(V3 / "membership.json") if m["block"].startswith("new")]
    grouped = defaultdict(list)
    for m in members:
        grouped[m["case_id"], m["policy"]].append(m)
    rows, diffs = [], []
    for (case, policy), mem in sorted(grouped.items()):
        mem.sort(key=lambda m: m["rank"])
        assert [m["rank"] for m in mem] == list(range(1, 7))
        seen = set()
        for m in mem:
            candidate = jobs[m["job_id"]]["candidate"]
            rows.append(dict(case_id=case, family=m["family"], policy=policy, rank=m["rank"],
                             job_id=m["job_id"], candidate_hash=fingerprint(candidate),
                             repeated_job_in_prefix=m["job_id"] in seen, **candidate))
            seen.add(m["job_id"])
        diffs.append(dict(case_id=case, policy=policy, family=mem[0]["family"],
                          logical_slots=6, unique_jobs=len(seen), duplicate_slots=6 - len(seen)))
    write_csv(OUT / "manifests/candidate_registry.csv", rows)
    write_csv(OUT / "manifests/candidate_budget.csv", diffs)
    roles = [dict(source=name, role="retrospective_development", may_tune=True,
                  may_claim_fresh=False) for name in ("prospective_v2", "prospective_v3",
                    "auditor_fixtures_v3", "auditor_fixtures_v3_posthoc", "external_v3")]
    write_csv(OUT / "manifests/data_roles.csv", roles)
    return dict(logical_slots=len(rows), unique_jobs=len({r["job_id"] for r in rows}),
                duplicate_slots_by_policy={p: sum(d["duplicate_slots"] for d in diffs if d["policy"] == p)
                                           for p in ("baseline", "repair", "no_extra")})


def run():
    protection = protect()
    result = dict(created_utc=utc_now(), protection=protection, frozen_inputs=frozen_inputs(),
                  historical=recount(), candidates=candidate_registry(),
                  runtime=dict(python=sys.version, executable=sys.executable, platform=platform.platform()))
    write_json(OUT / "manifests/asset_inventory.json", result)
    return {k: v for k, v in result.items() if k not in ("historical", "runtime")}
