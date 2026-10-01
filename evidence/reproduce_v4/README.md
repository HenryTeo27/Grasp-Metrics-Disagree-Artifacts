# Merged V4 Offline Evidence

Extract the evidence ZIP, then run from its top-level directory:

```text
python -B reproduce_v4/reproduce.py --out ../v4-recomputed
```

Requires Python 3.11, NumPy and Matplotlib. The release verification uses NumPy
1.26.4 and Matplotlib 3.11.2. There are no simulator or network requirements;
the verifier blocks MuJoCo imports and network connections. It checks every
packaged hash before and after its read-only analysis. Outputs go outside the
package. Expect seconds to a few minutes and under 1 GB RAM, excluding optional
PDF rendering. The verification JSON records what actually ran.

The public unit of evidence is the individual scored execution and future-use
label, not a screenshot. All 240 control, 720 Allegro candidate, 100 Fetch and
100 DexGraspBench execution records, 720 future labels, probability-sample
references, operating-point labels and the pre-future choice seal are included.
Scene-level Allegro results use 120 scenes, never 720 independent observations.
The script recomputes source tables, confusion matrices, paired intervals,
operating points and utility; it checks the claim ledger and regenerates all
three main figures. Figure 1 uses saved display-only simulation renderings.

This is **label-level aggregate reproduction**, not independent raw-trace
adjudication of the entire experiment. Three control raw traces are included as
examples. The full raw trace inventory records hashes and sizes but most raw
NPZs remain in the author's local research archive. No public download location
for that archive is asserted. Full raw audit access is consequently a release
limitation, not a completed reproducibility claim.

Dynamic reproduction additionally needs the exact runtimes, the repository
implementation and pinned third-party assets listed in `dependencies.md`.
No external dependency is silently downloaded or substituted. No new license
grant is invented for the author's source. Third-party model assets and the
unlicensed DexGraspBench checkout are not redistributed in this package.
