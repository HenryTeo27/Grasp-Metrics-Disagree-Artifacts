# When Grasp Metrics Disagree

**Physically Grounded Auditing for Robot Program Evaluation**

Teo Ee Hern, Tianjin University. Merged-paper V4, October 2026.
This is the successor to the preserved V3 paper, not the historical `paper_v4`
contact pilot or OpenHL V4/V4.1 training. The original root README is retained
unchanged because it belongs to the protected V3 release.

## Deliverables

- `dist/merged_hl_grasping_paper_v4.pdf`
- `dist/merged_hl_grasping_paper_v4_latex_source.zip`
- `dist/merged_hl_grasping_paper_v4_evidence.zip`
- `dist/merged_hl_grasping_paper_v4_verification.json`
- `dist/merged_hl_grasping_paper_v4_SHA256SUMS.txt`
- `notes/v4/completion_audit.md`, `reviewer_response_matrix.md`,
  `submission_readiness.md`, and `claim_evidence_ledger.csv`

Use the LaTeX source ZIP for source-based manuscript upload. The separate
evidence ZIP is a numerical/reproducibility supplement, not an arXiv upload.
No public hosting, submission, acceptance or new DOI is implied.

## Results

| Question | Frozen result | Boundary |
| --- | --- | --- |
| Record absence versus realized load | 8/8 same-dynamics pairs flip no-contact | Construct difference on registered apparatus |
| B5 versus strong B4, controls | Both match 240/240 reference labels | No incremental advantage; same-engine references |
| No-contact relative to no-load | 56 false rejections among 77 positives | Different targets, not universally wrong contact semantics |
| Historical excluded scenes | 0/85 rescued | Negative development evidence |
| Sealed candidate utility, K6 | Same choices 120/120; 10 usable / 120 | No B5 increment; 107 abstentions retained |
| Fetch | Native 100/100; added task 0 pass / 52 fail / 48 unknown | Damping torque gray zone; not native expert failure |
| Shadow / DexGraspBench | Native 66/100; added task 70 / 29 / 1 | Four identities, one invalid, environment-free portability |

The paper is a narrowed measurement/negative-result study. It does not claim a
new grasp controller, general dependence predictor, agent causal advantage or
learned-policy/hardware generalization. Five invalid Allegro candidate records
and one invalid DGB record remain visible.

## Offline Verification

Extract the evidence ZIP and run from its top-level directory:

```text
python -B reproduce_v4/reproduce.py --out ../v4-recomputed
```

Requires Python 3.11, NumPy and Matplotlib; no MuJoCo or network. The tested
offline runtime uses NumPy 1.26.4 and Matplotlib 3.11.2. Expect seconds to a few
minutes and under 1 GB RAM. It recomputes source tables, paired intervals,
operating points, sealed selection outcomes, the checked claim ledger and
three figures. It also rescores three full raw controls and independently
reconstructs 715 valid future endpoint flags. Expected main counts are above;
the generated `verification.json` must report PASS.

All individual score/reference/future labels are included. Most full raw NPZs
remain local, with hashes and sizes in the package; there is no asserted public
download URL. Four local fixed-case dynamic reruns are documented, but neither
a clean-machine install nor a full-matrix dynamic reproduction is claimed.
Third-party models and unlicensed DGB code are excluded with dependency pointers.
The author must decide licensing, complete raw publication and venue suitability.
