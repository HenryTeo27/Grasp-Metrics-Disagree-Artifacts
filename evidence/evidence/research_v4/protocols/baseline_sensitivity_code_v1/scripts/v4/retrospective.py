"""Read-only P1: every candidate associated with the V3 85/85 exclusions."""
from __future__ import annotations

from collections import Counter, defaultdict
import sys

import numpy as np

from .common import OUT, PAPER, V3, read_csv, read_json, sha256, write_csv, write_json, yes

sys.path.insert(0, str(PAPER / "scripts"))
from trace_integrity_v3 import summarize_checked


def intervals(mask):
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def longest(mask, dt):
    return max((b - a for a, b in intervals(mask)), default=0) * dt


def run(limit=None):
    cases = [r for r in read_csv(V3 / "case_results.csv")
             if r["block"].startswith("new") and r["k"] == "6"]
    excluded = {p: {r["case_id"] for r in cases if r["policy"] == p and
                   yes(r["contiguous_success"]) and not yes(r["clear_contiguous_success"])}
                for p in ("baseline", "repair")}
    union = sorted(excluded["baseline"] | excluded["repair"])
    selected = union if limit is None else union[:limit]
    case_map = {r["case_id"]: r for r in cases}
    members = [m for m in read_json(V3 / "membership.json") if m["case_id"] in selected]
    by_job = defaultdict(list)
    for m in members:
        by_job[m["job_id"]].append(m)
    columns = read_json(V3 / "protocol.json")["telemetry_columns"]
    field = {name: i for i, name in enumerate(columns)}
    rows, interval_rows = [], []
    for key, mem in sorted(by_job.items()):
        meta_path, trace_path = V3 / "trials" / (key + ".json"), V3 / "trials" / (key + ".npz")
        r = read_json(meta_path)
        with np.load(trace_path, allow_pickle=False) as z:
            a, e = z["samples"], z["telemetry"]
            calc = summarize_checked(a, z["step_index"], z["solve_time"], r["dt"],
                                     r["settle_steps"], r["final_step"],
                                     r["legacy_success"], r["initial_hand_contact"])
        if calc != r["temporal"]:
            raise RuntimeError(f"Historical trace inconsistency: {key}")
        if e.shape != (len(a), len(columns)) or not np.isfinite(e).all():
            raise ValueError(f"Malformed legacy telemetry: {key}")
        q = np.all(a[:, :4].astype(bool), axis=1) & ~a[:, 5].astype(bool)
        generated = e[:, field["environment_contact_count"]] > 0
        normal = e[:, field["environment_normal_sum_n"]]
        fz = e[:, field["environment_world_z_n"]]
        mass_weight = r["object_mass"] * 9.81
        net = e[:, [field[f"environment_world_{axis}_n"] for axis in "xyz"]]
        upward = fz > .01 * mass_weight
        zero = normal <= 1e-4
        global_q = r["legacy_success"] and not r["initial_hand_contact"] and calc["no_assistance"]
        duration = lambda v: float(np.sum(v) * r["dt"])
        q_max = longest(q, r["dt"])
        load_max = longest(q & upward, r["dt"])
        if not q.any():
            category = "no_local_common_interval"
        elif not generated[q].any():
            category = "no_environment_records_in_local_common_intervals"
        elif load_max >= .1:
            category = "sustained_measured_upward_load"
        elif np.all(zero[q & generated]):
            category = "only_below_floor_normal_records_full_wrench_unknown"
        else:
            category = "mixed_or_transient_full_wrench_unknown"
        rows.append(dict(job_id=key, case_id=r["case_id"], family=r["family"],
                         policy_slots=";".join(f'{m["policy"]}:{m["rank"]}' for m in mem),
                         global_common=global_q, native_success=r["legacy_success"],
                         clear_success=calc["clear_contiguous_success"], contiguous_success=calc["contiguous_success"],
                         local_common_s=duration(q), longest_local_common_s=q_max,
                         environment_record_s=duration(q & generated),
                         upward_load_gt_1pct_s=duration(q & upward), longest_upward_load_s=load_max,
                         below_floor_normal_record_s=duration(q & generated & zero),
                         max_normal_sum_n=float(np.max(normal[q])) if q.any() else 0.,
                         max_net_force_n=float(np.linalg.norm(net[q], axis=1).max()) if q.any() else 0.,
                         min_floor_clearance_m=float(e[q, field["primitive_floor_clearance_m"]].min()) if q.any() else "",
                         limited_diagnosis=category, full_wrench_verdict="UNKNOWN_PENDING_REPLAY",
                         trace_sha256=sha256(trace_path)))
        for index, (start, end) in enumerate(intervals(q)):
            interval_rows.append(dict(job_id=key, interval_id=index, start_row=start, end_row_exclusive=end,
                                      duration_s=(end-start)*r["dt"], qualifies_15s=(end-start)*r["dt"] >= 15-1e-9,
                                      global_common=global_q,
                                      environment_record_s=duration(generated[start:end]),
                                      upward_load_s=duration(upward[start:end]),
                                      longest_upward_load_s=longest(upward[start:end], r["dt"])))
    union_rows = []
    for case in selected:
        cr = [r for r in rows if r["case_id"] == case]
        eligible = [r for r in cr if r["global_common"] and r["longest_local_common_s"] >= 15-1e-9]
        union_rows.append(dict(case_id=case, family=case_map[case]["family"],
                               excluded_baseline=case in excluded["baseline"], excluded_repair=case in excluded["repair"],
                               unique_jobs=len(cr), common_eligible_jobs=len(eligible),
                               eligible_with_sustained_upward_load=sum(r["longest_upward_load_s"] >= .1 for r in eligible),
                               full_wrench_accounting="UNKNOWN_PENDING_REPLAY"))
    dest = OUT / "retrospective" / ("development_smoke" if limit else "complete")
    write_csv(dest / "excluded_case_union.csv", union_rows)
    write_csv(dest / "candidate_support_diagnosis.csv", rows)
    write_csv(dest / "common_intervals.csv", interval_rows)
    summary = dict(role="retrospective; limited original telemetry; not a C_NL verdict",
                   original_exclusions={p: len(v) for p, v in excluded.items()},
                   intersection=len(excluded["baseline"] & excluded["repair"]), union=len(union),
                   inspected_scenes=len(selected), unique_jobs=len(rows), logical_memberships=len(members),
                   interval_count=len(interval_rows), historical_traces_recomputed=len(rows),
                   all_eligible_candidates_show_sustained_upward_load=all(
                       r["common_eligible_jobs"] > 0 and r["eligible_with_sustained_upward_load"] == r["common_eligible_jobs"]
                       for r in union_rows),
                   categories=dict(Counter(r["limited_diagnosis"] for r in rows)),
                   telemetry_column_count=len(columns),
                   limitations=["No contact point or complete force/torque; net force cannot recover opposing loads",
                                "active_count is normal_force>1e-4, not efc_address",
                                "1% weight and 0.1s are old diagnostic thresholds, not a calibrated V4 gate",
                                "Load participation is not intervention-conditioned necessary dependence"])
    write_json(dest / "summary.json", summary)
    return summary
