# External Feasibility: Development Only

## Fetch

Pinned public state machine and original V3 dependencies are available. A
500-control-step / 10,000-physics-step raised-goal smoke reproduced the original
archived states/actions/native outcomes exactly. Observer-on/off execution was
also bit-identical. The smoke took 3.32 seconds for both executions and writes
only V4 metadata. This does not yet establish full-state sham restoration.

Native task, added retention task, privileged state feedback, mocap-weld arm,
2 kg object and high finger forces remain separate, explicit conditions. Only
MIT controller source is redistributable under its own license; installed
robot assets remain excluded from the new public package.

## Official robomimic BC-RNN Lift

The official model-zoo instructions require robomimic `v0.1` and robosuite
`offline_study`. The latter pins `mujoco-py==2.0.2.9`; upstream mujoco-py removed
Windows support at 2.0.2.0. This host is Windows, `wsl --list --quiet` returns no
installed distribution, and no Docker executable is available. No old-stack
rollout has been run. Upgrading its simulator without qualification would not
establish native reproduction. The existing simulation environment was not
modified to force compatibility.

Sources checked 2026-10-01:
- https://robomimic.github.io/docs/model_zoo/robomimic_v0.1.html
- https://raw.githubusercontent.com/ARISE-Initiative/robosuite/offline_study/setup.py
- https://raw.githubusercontent.com/openai/mujoco-py/master/README.md

## One Prespecified Compatibility Alternative

Before looking at any alternative outcomes, select the public DexGraspBench
Shadow-hand example snapshot as the single fallback feasibility check. It has
400 provided pregrasp/grasp/squeeze records spanning five object identities.
This is a static grasp/trajectory source, **not** a learned tabletop acquisition
controller. If admitted, the independent-learning-program claim is unsupported
and the formal task/source matrix must explicitly change before G2.

The native benchmark uses six signed external-force directions with gravity
disabled, mocap hand control and separate reset branches. Such forces are part
of its declared perturbation task, not hidden assistance. An added gravity
retention task is a different, separately named condition; native and added
scores cannot be pooled. The source README now distinguishes the main branch's
100 g / kp=5 setting from the old 30 g / kp=1 setting.

The optional full BODex object archive is 547,813,178 bytes. Its dataset card declares
CC-BY-NC-4.0. Inspection after cloning showed that all five example objects are
already included under `assets/example_object`, so the full archive was not
downloaded. The DexGraspBench repository does not expose a license through the
GitHub license API (404), so its code is not assumed redistributable. Private
research smoke and a source/hash/download manifest are possible; release must
exclude those files unless a license is established. No extra fallback search
is authorized by this bounded route.

Sources:
- https://github.com/JYChen18/DexGraspBench
- https://huggingface.co/datasets/JiayiChenPKU/BODex/blob/main/README.md

The pinned DexGraspBench commit is `d9ea6cf282de1f463c20fa54b4f68d7025bad40e`;
its Menagerie dependency commit is `9da3f77e7ef4cb588cefb3bae7209d20522062d8`.
HTTPS clone of the submodule failed with a connection reset; the nine required
Shadow meshes and their license were downloaded at the pinned revision instead.
Their per-file hashes and URLs are in the dependency manifest. This is not a
claim of a complete submodule checkout.

The isolated runtime is `C:/Users/User/.cache/codex-dexgraspbench-venv/`, with
MuJoCo 3.3.2, NumPy 1.26.4 and CPU Torch 2.2.2. All 11 observer instrumentation
tests pass on that runtime. The unmodified upstream native simulation function
was executed on the lexicographically first example (selected before outcomes),
with/without the read-only observer. Six reset segments / 4,200 physics steps
matched bit for bit, including the native success result, displacement and angle.
Maximum geometry/solve clock discrepancy was below 1.7e-17 m. This is a native
engineering smoke, not reproduction of a published aggregate benchmark score.

Status: Fetch feasible; robomimic native stack unavailable on this host;
DexGraspBench native example feasible. The added gravity-retention task, full-state
branches, mesh geometry reference and final adapter freeze still need work.
No formal external outcomes opened. The independent learned-acquisition-program
objective is unsupported with this fallback and must be amended explicitly at G2.
