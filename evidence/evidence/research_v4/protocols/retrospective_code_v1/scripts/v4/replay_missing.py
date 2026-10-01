"""Bounded additive replays; ineligible candidates remain in the accounting."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import time

from .common import OUT, V3, fingerprint, read_csv, read_json, sha256, utc_now, write_csv, write_json, yes
from .inventory import frozen_inputs


def run(workers=4):
    from .adapters import allegro
    from . import contact_observer
    sources = frozen_inputs()
    if sources["archive_mismatches"] or sources["current_v3_input_mismatches"] or sources["suite_mismatches"]:
        raise RuntimeError(sources)
    rows = read_csv(OUT / "retrospective/complete/candidate_support_diagnosis.csv")
    eligible = {r["job_id"] for r in rows if yes(r["global_common"]) and float(r["longest_local_common_s"]) >= 15-1e-9}
    jobs = [j for j in read_json(V3 / "jobs.json") if j["job_id"] in eligible]
    assert len(jobs) == len(eligible)
    spec = dict(observer_code_sha256=sha256(contact_observer.__file__), adapter_code_sha256=sha256(allegro.__file__),
                v3_input_manifest_hash=fingerprint(read_json(V3 / "protocol.json")["files"]),
                jobs={j["job_id"]: fingerprint(j) for j in jobs}, planned_job_count=len(jobs),
                selection="All candidates with global Q and at least 15 seconds of local Q; others provably fail unchanged Q",
                maximum_infrastructure_attempts=2, workers=workers, created_utc=utc_now(),
                role="retrospective supplementary measurement; does not generate fresh outcomes")
    lock = OUT / "retrospective/replay_lock.json"
    if lock.exists():
        saved = read_json(lock)
        if any(saved[k] != spec[k] for k in ("jobs", "observer_code_sha256", "adapter_code_sha256", "v3_input_manifest_hash")):
            raise RuntimeError("Replay specification changed; use an explicit deviation and a new attempt namespace")
    else:
        write_json(lock, spec, exclusive=True)
    dest = OUT / "retrospective/replays/complete_attempt_1"
    results, pending = [], []
    for job in jobs:
        path = dest / (job["job_id"] + ".json")
        if path.exists():
            r = read_json(path)
            if not all(r[k] == spec[k] for k in ("observer_code_sha256", "adapter_code_sha256", "v3_input_manifest_hash")):
                raise RuntimeError("Cached replay code mismatch")
            if r["job_spec_hash"] != fingerprint(job) or sha256(path.with_suffix(".npz")) != r["trace_sha256"]:
                raise RuntimeError("Cached replay input/output mismatch")
            results.append(dict(job_id=job["job_id"], case_id=job["case"]["case_id"],
                                equivalence_pass=r["equivalence_pass"], planned_steps=r["planned_steps"],
                                trace_bytes=r["trace_bytes"], elapsed_s=r["elapsed_s"], cache_hit=True))
        else:
            pending.append(job)
    tic = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(allegro.execute, j, dest, compare_archive=True): j for j in pending}
        for f in as_completed(futures):
            j = futures[f]
            try:
                r = f.result()
                results.append({k: r[k] for k in ("job_id", "case_id", "equivalence_pass", "planned_steps", "trace_bytes", "elapsed_s")} | {"cache_hit": False})
            except Exception as error:
                results.append(dict(job_id=j["job_id"], case_id=j["case"]["case_id"],
                                    equivalence_pass=False, planned_steps=0, trace_bytes=0, elapsed_s=0., cache_hit=False,
                                    error=f"{type(error).__name__}: {error}"))
            if len(results) % 10 == 0:
                print(f"Replay evidence {len(results)}/{len(jobs)}, wall {time.perf_counter()-tic:.1f}s", flush=True)
    fields = ["job_id", "case_id", "equivalence_pass", "planned_steps", "trace_bytes", "elapsed_s", "cache_hit", "error"]
    write_csv(OUT / "retrospective/replay_equivalence.csv", sorted(results, key=lambda r: r["job_id"]), fields)
    failures = [r for r in results if not r["equivalence_pass"]]
    after = frozen_inputs()
    if after != sources:
        raise RuntimeError("Frozen runtime changed during supplementary replay")
    result = dict(planned_replays=len(jobs), completed=len(results), equivalence_passes=sum(r["equivalence_pass"] for r in results),
                  failures=failures, trace_bytes=sum(r["trace_bytes"] for r in results), elapsed_s=time.perf_counter()-tic,
                  unreplayed_common_condition_failures=len(rows)-len(jobs), full_candidate_denominator=len(rows),
                  source_lock_unchanged=True, cache_hits=sum(r["cache_hit"] for r in results))
    write_json(OUT / "retrospective/replay_completion.json", result)
    return result
