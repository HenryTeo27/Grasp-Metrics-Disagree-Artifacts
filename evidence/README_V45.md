# Merged V4.5: Final Editorial Release

**When Grasp Metrics Disagree: Contact, Load, and Retention in Simulation**

V4.5 is an editorial consolidation of existing V3/V4 evidence, not a new
experiment, controller version, or evaluator protocol. The main narrative
centers on three measurement targets and two negative primary comparisons.
V3 model/library results remain a clearly labeled historical subsection and
full supplementary tables. The original project `README.md` is unchanged.

## Manuscripts

The `dist/` release in the working project supplies:

- `merged_hl_grasping_paper_v4_5.pdf`: author main manuscript.
- `merged_hl_grasping_paper_v4_5_supplement.pdf`: complete supporting material.
- `merged_hl_grasping_paper_v4_5_review_preparation.pdf`: author fields removed.
- `merged_hl_grasping_paper_v4_5_supplement_review_preparation.pdf`: matching supplement.
- `merged_hl_grasping_paper_v4_5_latex_source.zip`: independently buildable sources.
- `merged_hl_grasping_paper_v4_5_evidence.zip`: label-level offline evidence.
- `merged_hl_grasping_paper_v4_5_core_raw.zip`: 240 final controls and eight
  representation partners, with original raw NPZs and hash/size manifest.

No conference submission, public hosting, or new code-license grant is made.
The main paper uses an IEEE two-column layout. IROS 2027 page limits,
anonymity, supplementary-upload and disclosure rules require confirmation
against the actual call before submission. Prior reports remain cited in
normal third-person form, including in the review-preparation PDFs.

## Evidence Boundary

The nominal control comparison is 240 assigned cases, with 77 no-load
positives and 163 negatives. Literal no-contact rejects 56 positives.
Clearance, normal-only, full-wrench and integrated monitoring all match those
nominal labels: no unique integrated-monitor benefit is established.

On the fresh 120-scene Allegro K6 task, B2/B4/B5 make identical choices:
10 usable returns, three valid failed returns, and 107 abstentions. Native
selection instead gives 15 usable, 25 failed and 80 abstentions. Higher
conditional success does not mean higher all-scene usability. Both original
primary B5--B4 differences are zero, without an equivalence claim. The
retrospective rescues 0/85 scenes; only 177 of its 510 slots have full load
replays, and 333 fail the unchanged common conditions.

V3's 37/360 versus 48/360 no-contact comparison is historical, with all 11
gains in spheres. Its candidate budget, compiled physical model and bootstrap
are separate from V4. No datasets are pooled or relabeled.

## Offline Reproduction

Extract the evidence ZIP and run from its top-level directory:

```text
python -B reproduce_v4/reproduce.py --out ../v4-recomputed
```

The output directory must be new. Requires Python 3.11, NumPy and Matplotlib.
The verified release environment uses NumPy 1.26.4 and Matplotlib 3.11.2.
The original verifier blocks simulator imports and network connections,
checks package hashes before/after, recomputes tables and intervals, checks
the sealed decisions and claim ledger, and regenerates the original V4
figures. It also rescores three raw primitive-control examples. It does not
simulate any experiment or independently relabel the entire matrix.

The publication-only V4.5 composition can then be run separately:

```text
python -B scripts/v45_editorial.py figures
```

This creates V4.5 figures from the frozen records and saved image arrays. It
does not import scientific modules or a simulator. Run the original verifier
before this optional command: the optional figure command writes presentation
outputs within the package and consequently changes its original manifest
state. An untouched extraction remains the reproducibility input.

The optional core-raw ZIP supplies all 248 controlled raw traces but is not
needed for the aggregate verifier. It adds source evidence access, not a
claim of 248 new independent raw reconstructions. Most natural-task,
retrospective and calibration raw traces remain local. The full inventory in
the label package records their sizes/hashes; an inventory is not raw data
access. Its `included` flags refer to the label ZIP, not to the separate
core-raw companion. Full raw-matrix adjudication, clean-machine dynamic reproduction,
and complete public raw hosting are not claimed.

## Provenance and Licensing

Scientific inputs, labels, code and original paper releases were protected by
before/after hashes during editorial work. Existing post-failure recovery
remains separately hashed and disclosed. Exact source versions, available
component licenses and limitations are in `dependencies.md` in the evidence
archive and `reproduce_v4/dependencies.md` in the working project.

FetchExpert's pinned source and two prior-report DOIs were checked against
their primary records on 2026-10-01. The prior DOIs are
10.5281/zenodo.20922238 and 10.5281/zenodo.20922501. Third-party robot model
assets and the unlicensed DexGraspBench checkout are not redistributed.

The working-project completion report under `notes/v45/` records actual
verification outcomes and final package hashes. It does not substitute for
the frozen research records or imply acceptance by IROS.
