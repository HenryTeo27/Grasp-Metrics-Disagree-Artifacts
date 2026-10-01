"""Add full telemetry to frozen Allegro jobs without modifying the V3 runner."""
from __future__ import annotations

import sys
import time

import numpy as np
import mujoco

from ..common import OUT, PAPER, REPO, V3, fingerprint, output_path, read_json, sha256, write_json
from ..contact_observer import ContactRecorder, body_scale
from .. import contact_observer

sys.path.insert(0, str(PAPER / "scripts"))
import prospective_v3 as frozen

BaseObserver = frozen.Observer


def planned_steps(candidate, anchor, dt):
    s = anchor["stages"]
    if candidate["runner"] == "staged":
        keys = ("pre_steps", "ff_ramp_steps", "ff_hold_steps", "thumb_ramp_steps",
                "thumb_hold_steps", "lift_ramp_steps")
        return 100 + sum(int(s[k]) for k in keys) + int(s.get("lift_hold_steps", 1400)) + int(
            s.get("support_ramp_steps", 1000)) + int(s.get("support_hold_steps", 7600))
    hold = int(round((15 + candidate["extra_s"]) / dt))
    total = sum(int(s[k]) for k in ("settle_steps", "contact_steps", "grip_steps"))
    if "bridge_ctrl" in anchor:
        keys = ("micro_ramp_steps", "micro_hold_steps", "bridge_ramp_steps", "bridge_hold_steps",
                "lift_ramp_steps", "lift_hold_steps", "support_ramp_steps")
        return total + sum(int(s[k]) for k in keys) + max(hold, int(s.get("support_hold_steps", hold)))
    if "feedback" in anchor and "cradle_ctrl" in anchor:
        keys = ("micro_ramp_steps", "micro_hold_steps", "cradle_ramp_steps", "cradle_hold_steps", "support_ramp_steps")
        return total + sum(int(s[k]) for k in keys) + int(s.get("lift_ramp_steps", s.get("final_ramp_steps"))) + hold
    if "support_ctrl" in anchor or "feedback" in anchor:
        keys = ("micro_ramp_steps", "micro_hold_steps", "final_ramp_steps", "support_ramp_steps")
        return total + sum(int(s[k]) for k in keys) + (hold if "feedback" in anchor else max(hold, int(s.get("support_hold_steps", hold))))
    if "micro_ctrl" in anchor:
        return total + sum(int(s[k]) for k in ("micro_ramp_steps", "micro_hold_steps", "final_ramp_steps")) + hold
    if candidate["derived"]:
        return total + 250 + 350 + 500 + int(s["ramp_steps"]) + hold
    return total + int(s["ramp_steps"]) + hold


def execute(job, destination, *, compare_archive=False, snapshot_time=8.):
    destination = output_path(destination)
    jp, zp = destination / (job["job_id"] + ".json"), destination / (job["job_id"] + ".npz")
    if jp.exists() or zp.exists():
        raise FileExistsError(f"Refuse to replace an attempt: {job['job_id']}")
    start = time.perf_counter()
    captured = []
    anchor = read_json(REPO / job['candidate']['anchor'])

    class RichObserver(BaseObserver):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            roles = [{"other": 0, "thumb": 1, "long": 2, "palm": 3}[r] for r in self.body_regions]
            snapshot_step = (planned_steps(job['candidate'], anchor, self.model.opt.timestep)-round(4/self.model.opt.timestep)
                             if snapshot_time == 'late' else int(round(snapshot_time/self.model.opt.timestep)))
            self.recorder = ContactRecorder(self.model, self.obj, roles,
                                            snapshot_step=snapshot_step)
            self.last_data = None
            captured.append(self)

        def step(self, model, data, nstep=1):
            if nstep != 1:
                raise ValueError("Every physics solve must be observed")
            self.recorder.before_step(data, self.step_count)
            super().step(model, data, nstep)
            self.recorder.after_step(data)
            self.last_data = data

    prior = frozen.Observer
    frozen.Observer = RichObserver
    try:
        result = frozen.execute(job, save=False)
    finally:
        frozen.Observer = prior
    observer = captured[0]
    planned = planned_steps(job["candidate"], anchor, result["dt"])
    if planned != result["final_step"]:
        raise RuntimeError(f"Anchor schedule mismatch: planned {planned}, recorded {result['final_step']}")
    recorder = observer.recorder
    data = recorder.arrays()
    final_flag = mujoco.mjtState.mjSTATE_INTEGRATION
    final_state = np.empty(mujoco.mj_stateSize(observer.model, final_flag))
    mujoco.mj_getState(observer.model, observer.last_data, final_state, final_flag)
    data['final_integration_state'] = final_state
    data.update(samples=np.asarray(observer.rows), legacy_telemetry=np.asarray(observer.extra),
                legacy_step_index=np.asarray(observer.indices), legacy_solve_time=np.asarray(observer.times))
    equivalence = None
    if compare_archive:
        original = read_json(V3 / "trials" / (job["job_id"] + ".json"))
        with np.load(V3 / "trials" / (job["job_id"] + ".npz"), allow_pickle=False) as z:
            equivalence = {"samples": np.array_equal(data["samples"], z["samples"]),
                           "telemetry": np.array_equal(data["legacy_telemetry"], z["telemetry"]),
                           "step_index": np.array_equal(data["legacy_step_index"], z["step_index"]),
                           "solve_time": np.array_equal(data["legacy_solve_time"], z["solve_time"]),
                           "metrics": result["metrics"] == original["metrics"],
                           "temporal": result["temporal"] == original["temporal"]}
    output_path(zp)
    np.savez_compressed(zp, **data)
    meta = dict(job=job, result=result, observer=recorder.metadata(), planned_steps=planned,
                terminal_reason="controller_schedule_completed", source_id="allegro_frozen_library",
                length_scale_m=body_scale(observer.model, observer.object_geom),
                archive_equivalence=equivalence, equivalence_pass=all(equivalence.values()) if equivalence else None,
                trace_sha256=sha256(zp), job_spec_hash=fingerprint(job), elapsed_s=time.perf_counter()-start,
                trace_bytes=zp.stat().st_size,
                observer_code_sha256=sha256(contact_observer.__file__), adapter_code_sha256=sha256(__file__),
                v3_input_manifest_hash=fingerprint(read_json(V3 / "protocol.json")["files"]),
                split_role="retrospective_development" if compare_archive else job["block"],
                controller_state="Open-loop command tape for branching; no policy execution on restored branches")
    meta.update(final_state_flag=int(final_flag), final_time_s=float(observer.last_data.time))
    write_json(jp, meta, exclusive=True)
    return dict(job_id=job["job_id"], case_id=job["case"]["case_id"],
                equivalence_pass=meta["equivalence_pass"], clock_error=meta["observer"]["geometry_clock_max_error"],
                planned_steps=planned, trace_bytes=meta["trace_bytes"], elapsed_s=meta["elapsed_s"],
                support_paths=meta["observer"]["support_paths"])


def replay_one(job_id=None):
    jobs = read_json(V3 / "jobs.json")
    if job_id is None:
        from ..common import read_csv, yes
        rows = read_csv(OUT / "retrospective/complete/candidate_support_diagnosis.csv")
        eligible = sorted(r["job_id"] for r in rows if yes(r["global_common"]) and float(r["longest_local_common_s"]) >= 15-1e-9)
        job_id = eligible[0]
    job = next(j for j in jobs if j["job_id"] == job_id)
    return execute(job, OUT / "retrospective/replays/attempt_1", compare_archive=True)
