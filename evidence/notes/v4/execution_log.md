# Merged Paper V4 Execution Log

## Scope And Authorization

2026-10-01: the user explicitly requested execution of the complete integrated
V4 research/development/manuscript plan. The planning-only status in the original
plan describes its creation, not this subsequent authorization.

Plan: `agents/task/merged_hl_grasping_paper_v4_final_research_execution_plan.md`.
Namespace: merged-paper V4 only. No retraining, historical overwrites, simulator
physics retuning, hidden assistance, or retrospective relabeling as blind tests.

## Status

| Stage | Status | Evidence |
| --- | --- | --- |
| P0 protection / inventory / feasibility | COMPLETE | Historical protection retained; U1 stopped for absent version-ranking divergence; U2 frozen from development feasibility |
| P1 complete excluded-case diagnosis | COMPLETE | Final nominal adjudication: 510 candidate FAIL, 0/85 scenes rescued; 177 equivalent full-wrench replays, 333 unchanged common-condition failures without guessed wrench values |
| P2 observer / contracts / calibration | COMPLETE | 89 qualification tests; 80 full-state controls, numerical variants, natural pilots, B0-B7 and ablations |
| G2 protocol freeze | COMPLETE | 1028 existing code/input hashes and five designs frozen before formal outcomes; original lock unchanged |
| P3 controls / counterfactuals | COMPLETE | 240 controls, 48 fixed branches, eight representation pairs; no B5 gain over B4 |
| P4 external validation | COMPLETE, NARROWED | 720 Allegro executions / 120 scenes, 100 Fetch, 100 DGB; learned-acquisition-source objective unsupported |
| P5 utility route | COMPLETE, NEGATIVE | 2520 choices sealed before 720 future records; B4/B5 identical 120/120 at K6; 10/120 usable |
| P6 manuscript / claims | COMPLETE, NARROWED | 12-page manuscript with generated tables, three figures and negative-result framing |
| P7 independent reproduction / release | IN_VERIFICATION | Label-level offline reproduction and four fixed dynamic checks PASS; independent source ZIP and final handoff audit pending |

## Initial Checks

- Read the complete 729-line integrated plan and V3 completion/claim ledgers.
- Simulation interpreter confirmed: CPython 3.11.1, NumPy 2.4.6, MuJoCo 3.8.0,
  `C:/Users/User/.cache/codex-grasp-audit-venv/Scripts/python.exe`.
- Fetch dependencies are separately installed under the V3 external directory.
  Torch, robosuite and robomimic are not installed in the simulation interpreter.
- Old analyzer writes historical reports; it must not be called in place.
- New inventory writes only V4 metadata and uses streaming hashes without copying
  multi-GB evidence archives. Archived dependency binaries are excluded from this
  first protection scope; their existing input locks are retained.

Scientific support and engineering completion will be reported separately.

## First Vertical Slice

Historical protection manifest covers 7,214,382,726 bytes without duplicating
them. V3 CSV recount reproduces 37/48, eleven sphere gains and the identical
85-scene exclusion sets. Candidate registry finds no duplicate-filled budgets.
Read-only P1 analysis and supplementary replay are detailed in
`telemetry_gap_report.md`; candidate differences in `baseline_repair_diff.md`.

The no-load evaluator now separates VALID/INVALID trace status from
PASS/FAIL/INDETERMINATE physical verdicts. It preserves a supplied task's common
conditions, requires a planned horizon, and measures definite/possible
continuous intervals. Current thresholds are explicitly development defaults,
not the G2 calibration. Tests include exact 15 seconds, interrupted holds,
missing/duplicate/time-corrupt rows, assistance and oracle-identity irrelevance.

Storage decision, 2026-10-01: the user explicitly rejected putting V4 on the F
hard disk. V4 remains in the C-drive project namespace. The user authorized
removing retired pre-merge papers, merged V1/V2 releases, and unused historical
code/log/test data, with possibly reusable material consolidated on F:/project.

## Authorized Historical Relocation

This storage request changes the original preserve-in-place constraint only
for retired material. The original protection manifest remains immutable.
`scripts/archive_legacy_research.ps1` previews explicit groups, checks all 317
current frozen runtime input hashes and the latest V3 release hashes, archives
retired material to `F:/project/Dexterous-Hand-Control-Sim-history-20261001`,
verifies every archive entry's SHA256, and only then removes unchanged source
files. Six V3/V4 runtime anchor JSONs in `results/` remain at their exact paths.
No CAD, active simulator/model/config, merged historical evidence, or V4 output
is moved. Regenerable merged build caches are removed separately. Retired V1/V2
release files are archived because historical release scripts refer to them.
The archive receipts will distinguish relocation from unchanged-in-place
protection; no missing historical file will be silently excused.

Execution status: completed. Ten groups / 110,135 files / 14,031,823,576 source
bytes were verified and removed from C after archiving; approximately 3.76 GiB
of redundant build caches was deleted. The latest V3 release, active V4 work and
all 317 current frozen inputs are preserved. `dist/` now contains only the five
V3 release files. All six live result anchors remain. Archive receipts and the
repository archive index record how to recover individual old files; old release
scripts may require restoration of their retired V1/V2 inputs.

Final cleanup checks: original protection verification reports
`PASS_WITH_AUTHORIZED_RELOCATION` for 9,201 entries, with no changed files,
unexplained missing files, or archive errors. Current and archived frozen inputs
and V3 suite hashes all match. The new audit does not repair or excuse unrelated
historical runtime-lock failures disclosed before this work.

## Completed Development Comparisons

`calibration/baselines_v1/` compares the same registered 80 states, not a new N.
B3 geometric separation, B4 full wrench and B5 all agree with the independent
implementation: 25 PASS / 55 FAIL. B2 has 18 false rejections *relative to the
no-load specification*, not violations of its own no-contact definition. B0/B1
are explicitly common-Q proxies in this apparatus, not a native benchmark.
All nominal B5 ablations have the same verdicts here; no added method benefit
has been established. The calibrated tolerance remains 1e-4 PASS / 1e-2 FAIL
for force divided by weight and torque divided by weight times body-frame scale.

The static B6 LP uses inscribed point-contact friction cones and bounded actuator
forces. It calls all 67 reached control states feasible, including 10 that fail
the removed-support continuation. B7 uses six extra one-second, one-weight
signed force probes with target-environment contact removed, and separates
57 retained / 10 dependent states on this development set. Its cost is 201,000
additional steps, not free telemetry. The same 13 unreached states remain in
both records. B6 is not applicable to the current natural Allegro models with
unbounded actuators; capacity limits are not invented for convenience.

`calibration/sensitivity_v1/` uses eight original states with nominal, half-dt,
double-dt and looser-solver variants: 32 executions, not 32 independent designs.
All categorical labels are stable; 28 reached branch pairs are bit-exact under
nominal sham. Cubic 0.2-second mocap support withdrawal agrees with instantaneous
contact removal on these cases, without asserting the interventions equivalent.
The 20 exclusion-selected natural states also retain their 17 DEPENDENT / three
BOTH_RETAIN labels under half/double dt and half solver iterations. This is not
a prevalence sample. B7 agrees on those 20 at a further 60,000 steps; a simple
pre-branch load threshold also separates them, so no new dependence-prediction
algorithm is claimed.

Four additional, registered single-burst temporal apparatus cases have 16.9 s
accumulated versus 9.9 s contiguous unloaded common conditions. These are separate
development qualification, not additions to the original 80. The same 80 were
then rerun under the latest instrumentation in `requalified_controls_v2/`;
complete per-step MuJoCo integration states match observer-off execution bit
for bit, and all reference/B4/B5/CF counts are unchanged.

## External And Utility Qualification

The Shadow-hand added gravity-retention smoke has a free mesh object, unchanged
upstream staged closure, then gravity on and fixed squeeze commands for 18 s.
It passes the declared 15-second criterion; observer on/off and full-state sham
are bit-identical. This is not native acquisition or a learned policy. Its FC
model has no environment collision geoms, so contact withdrawal is an audited
no-op and cannot establish sensitivity to environmental support.

The Fetch adapter retains native target damping 0.01 on all six free DOFs. The
meter now includes solve-state and implicit-endpoint damping wrench magnitudes;
independent Jacobian and raw coefficient/velocity reconstruction tests qualify
the conversion. No friction, mass, damping or controller is changed. The raised
smoke still returns INDETERMINATE because damping torque lies in the declared
gray band. Independent vertex geometry and raw wrench/passive reconstruction
agree, and the historical/control-state traces and sham are bit-exact. Tolerances
are not widened to make Fetch pass.

Before final evaluation, branch eligibility was corrected to use initial/prefix
conditions and local Q, never the future native episode result. This prevents
silently excluding future BOTH_FAIL cases. Existing development cases were all
future-native successes, so their reported cells do not change; tests explicitly
cover a future-native-failure with an eligible prefix.

The real pool contains only baseline and repair; No-extra duplicates baseline.
All three historical scores promote repair, so U1 is stopped. U2 uses the fixed
repair K=6 pool with K=1/3 prefixes and first-PASS/else-abstain acceptance. Its
pilot has 141 native acceptances versus 48 no-contact acceptances and 93 differing
decisions in old 360 scenes. A separate three-category continuation smoke exactly
replays old metrics before evaluating a new 15-second hold-last-command task
with target-environment contact removed. Native-failure and native-only examples
fail, and the clear-pass example retains. This establishes executable endpoints,
not a utility estimate. Final U2 choices must be sealed before new future outcomes.

The independent learned-acquisition-source objective is unsupported on this host
and is explicitly narrowed in the final protocol.

## G2 Frozen And Formal Execution Started

The final qualification suite passed 89 tests. The three existing Allegro utility
traces were independently reconstructed from raw contact wrenches and primitive
geometry, with identical common-Q and matching PASS/FAIL/FAIL results. A new
predeclared Fetch development seed 900001 preserves the native goal and succeeds
at the native task, but fails the added retention task; observer-on/off execution
is identical. Repeating the already exposed first DGB record through the final
driver preserves its native result and added-task/sham outcome.

G2 was sealed before any formal outcomes. The protocol SHA-256 is
`ffc60fe94dca45e826c2f864865cbeb7c749b7a11b6f05784b9c6f24b896b9a0`.
It binds 1,028 source/dependency files and all five input-only design files:
240 controls, 120 fresh Allegro scenes with six genuine repair candidates each,
100 native-goal Fetch seeds, and 100 DGB records across four held-out identities.
The 108 counterfactual states and 90 natural reference entries are fixed subsets,
not extra independent scenes. No independent human annotation or blinding is
claimed. U2 choices must be sealed before all 720 future-use outcomes.

The pre-test risk ceiling and practical effect threshold are both 0.05; the two
primary comparisons use 97.5% two-sided paired bootstrap intervals with 10,000
draws and analysis seed 2026100101. The fixed sample budget is not a certificate
of low population risk or 5-point statistical power. Operating-point curves,
eight representation pairs and intermittent-control proportions are registered.

At this checkpoint the formal batches were launched with locked sources. No
policy, threshold, split or physics tuning was allowed from their outputs.

## Formal Results And Bounded Release Checks

All 1160 nominal execution records are complete and the original protocol and
raw hashes pass read-only verification. Controls have 77 reference positives
and 163 negatives; B4 and B5 match all 240, while no-contact rejects 56 of the
77 positives. All eight inactive-margin representation pairs preserve complete
integration states but flip no-contact. The control branch subset contains 33
both-retain, six dependent and nine unreachable states.

Fetch native tasks succeed 100/100; added no-load gives 0 PASS, 52 FAIL and 48
INDETERMINATE because target damping torque remains in the frozen gray band.
DGB native tests pass 66/100, while the separately defined gravity-retention
task gives 70 PASS, 29 FAIL and one invalid/indeterminate record. Its environment
withdrawal is a no-op. Its unmetered native/staging costs are explicitly excluded
from exhaustive budget claims.

Allegro completed all 720 fixed candidate executions. Five nanometer-scale
geometry-reconstruction inconsistencies fail the frozen assertion; the original
code is preserved and a registered post-failure bookkeeping wrapper stores
INVALID/INDETERMINATE, without replacement or threshold relaxation. See
`execution_recovery.md`. All native results remain separately available.

The original selector sealed all 2520 method/prefix choices at
2026-09-30T23:06:05.325568+00:00 before any future outcomes. All 720 future
records are now complete: 715 physical continuations and five invalid-input
records. At K6, B5/B4 accept 13/120 and return 10/120 usable outcomes with 107
abstentions. All 120 choices are identical; both primary effects are zero.
Native-gate selection accepts 40 and returns 15 usable outcomes. The observed
pool oracle is 49/120 and is a lower bound because invalid futures remain.

Offline package attempt 1 passed hash checks, source summaries, paired
10,000-draw intervals, all 60 operating points, 715 endpoint-flag reconstructions,
three raw control rescoring/reference checks and all three regenerated figures.
It explicitly blocks network access and simulator imports. Four fixed first-case
dynamic checks passed in the declared existing isolated runtimes; these are not
a clean-machine installation or a full-matrix rerun. Most raw traces remain local
with a hash/size inventory; no public hosting claim is made.
