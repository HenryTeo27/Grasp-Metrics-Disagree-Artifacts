"""Read-only runtime checks and bounded external engineering smoke."""
from __future__ import annotations

import importlib.util
import platform
import sys
import time

import numpy as np

from .common import OUT, PAPER, read_json, sha256, utc_now, write_json


def fetch_smoke():
    sys.path.insert(0, str(PAPER / "scripts"))
    import external_v3_fetch_audit as old
    old.verify_inputs()
    protocol = read_json(old.OUT / "protocol.json")
    spec = importlib.util.spec_from_file_location("p0_frozen_fetch_expert", old.OUT / "upstream/fetch_expert.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old.gym.register_envs(old.gymnasium_robotics)
    scene = protocol["scenes"][1]
    start = time.perf_counter()
    native = old.rollout(scene, protocol, module.FetchExpert, False)
    recorded = old.rollout(scene, protocol, module.FetchExpert, True)
    same = all(np.array_equal(x, y) for x, y in zip(native[:3], recorded[:3]))
    if not same:
        raise RuntimeError("Frozen Fetch observer changed rollout")
    with np.load(old.OUT / "rollouts" / scene["id"] / "trace.npz", allow_pickle=False) as prior:
        old_equal = all(np.array_equal(x, prior[field]) for x, field in zip(recorded[:3],
                          ("control_states", "actions", "native_success")))
    result = dict(source="public_fetch_state_machine", split_role="engineering_smoke_excluded_from_final",
                  scene=scene, observer_on_off_bit_equal=same, original_trace_bit_equal=old_equal,
                  native_success_final=bool(recorded[2][-1]), control_steps=len(recorded[1]),
                  physics_steps=len(recorded[3].samples), elapsed_s=time.perf_counter()-start,
                  source_sha256=sha256(old.OUT / "upstream/fetch_expert.py"),
                  state_restore="Not yet tested; observer equality does not establish sham equivalence",
                  controller_license="MIT", assets_redistribution="Excluded; retain upstream license limits")
    write_json(OUT / "external/fetch/smoke/native_reproduction.json", result)
    return result


def run(smoke=False):
    import mujoco
    result = dict(checked_utc=utc_now(), executable=sys.executable, python=platform.python_version(),
                  numpy=np.__version__, mujoco=mujoco.__version__, automatic_install=False,
                  platform=platform.platform(),
                  modules={name: bool(importlib.util.find_spec(name))
                           for name in ("torch", "scipy", "robosuite", "robomimic")})
    if smoke:
        result["fetch"] = fetch_smoke()
    write_json(OUT / "manifests/doctor.json", result)
    return result
