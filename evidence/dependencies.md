# Dynamic Dependencies and Rights Boundary

No third-party mesh, checkpoint, object dataset, installed package tree or
DexGraspBench implementation is redistributed. Offline label-level reproduction
does not require any of them. The original G2 lock's `code_hashes` records the
exact per-file local inputs; the compact package verifies its included subset,
not absent asset hashes. Missing dynamic assets mean **NOT AVAILABLE**, not PASS.

## Declared Runtimes

- Main controls / Allegro / Fetch: CPython 3.11.1, NumPy 2.4.6, MuJoCo 3.8.0,
  SciPy 1.17.1; Windows 11 host (platform API reports Windows 10 build 26200).
- DexGraspBench: CPython 3.11.1, NumPy 1.26.4, MuJoCo 3.3.2, SciPy 1.17.1,
  CPU Torch 2.2.2. Separate virtual environment, not mixed with the main runtime.
- Offline figures: NumPy 1.26.4, Matplotlib 3.11.2. MuJoCo is blocked by the
  offline script even if that optional package is installed.

Local dynamic release checks use the existing isolated environments. They are
fixed-case reruns, not a clean-machine reinstall or a repeat of the full matrix.
The repository's original model/config hierarchy is required for dynamic use.

## Sources

- Fetch controller: [e-cagan/franka-il-rl](https://github.com/e-cagan/franka-il-rl/tree/3e2dd8c2e5f24702081867d82a78eb1264534f94),
  `experts/fetch_expert.py`, commit `3e2dd8c2e5f24702081867d82a78eb1264534f94`;
  controller code MIT. Frozen source SHA256 is
  `5d9682b52e43dbee2d2dd81d83b44b14cdc70945c9069de3b3958df8a852865b`.
- Fetch environment: [Gymnasium-Robotics v1.4.2](https://github.com/Farama-Foundation/Gymnasium-Robotics/tree/v1.4.2),
  commit `42eae53b2b27321d29090c219ce2f675c596de77`, Gymnasium 1.2.3.
  Wheel SHA256 `a1743530431cb377e6b3b956d284bc96436fc68bac1648ef205054c178e7dc4b`.
  Python package code is MIT, but inherited Fetch model provenance is less
  precise; Fetch's asset package declares CC BY-NC-ND 4.0. Do not apply the code
  license to all meshes. V4 preserves the sampled native goal; the older V3
  demonstration's raised-goal modification is not used in the formal V4 run.
- Allegro model: [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie),
  the repository's existing pinned local Allegro checkout. Exact XML/mesh hashes
  are in the G2 lock. No complete upstream Allegro commit provenance is asserted
  beyond those input hashes. Original license notices remain with that local
  dependency; the compact release excludes the model and does not relicense it.
- Shadow pose source: [DexGraspBench](https://github.com/JYChen18/DexGraspBench/tree/d9ea6cf282de1f463c20fa54b4f68d7025bad40e),
  commit `d9ea6cf282de1f463c20fa54b4f68d7025bad40e`. No repository license grant
  was found in the pinned checkout; its code and example objects are excluded.
  Formal object identity/input hashes are in `protocols/final_dexgraspbench.json`.
- Shadow meshes: Menagerie commit `9da3f77e7ef4cb588cefb3bae7209d20522062d8`.
  `evidence/research_v4/external/dexgraspbench/dependency_manifest.json` contains
  exact per-file HTTPS URLs, byte sizes and hashes for the nine meshes and
  license retrieved after the complete submodule clone failed. The partial
  retrieval is not presented as a complete dependency checkout.
- The optional [BODex object archive](https://huggingface.co/datasets/JiayiChenPKU/BODex)
  was not downloaded or used; its dataset card's CC-BY-NC-4.0 does not establish
  redistribution rights for the entire DexGraspBench repository.

No public hosting, code-license selection or paper submission is performed by
this release procedure. Those remain author decisions.
