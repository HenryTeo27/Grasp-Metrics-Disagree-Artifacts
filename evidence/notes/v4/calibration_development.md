# Calibration Development, Not Formal Results

## First Free-Object Vertical Slice

Eight development apparatus instances were recorded for 18 seconds each with
two actuated pads and a single free six-DOF box. No target guides, target
actuators, or target state writes are used after reset. Their retention task
starts from an explicit pregrasp; it does not claim acquisition from a table.
These apparatus debugging runs are not the planned 80-instance calibration set.

All eight observer-on trajectories matched observer-off target states bit for
bit. The raw contact reconstruction uses a separate vectorized frame/wrench
implementation, explicit eight-vertex plane geometry, and a separate interval
loop. It matched common conditions and recorded wrench values in all eight;
the largest geometry discrepancy was below 3e-17 m. This is separate
implementation within the same simulator, not external physical truth, a
separate annotator, or human labeling.

The initial intended inactive-margin control had only a 5 mm gap. The freely
held object settled/slipped about 7.34 mm over 18 seconds, so this instance
eventually had real floor load and correctly failed the no-load retention
contract. It is retained with its observed result, not relabeled by apparatus
name. The next development revision increases this gap and widens only that
apparatus's inactive contact-record band. This does not change a historical
robot's physics or any audit threshold.

## Full-State Branch Pilot

At fixed t0=8 s, seven eligible cases admitted a 3 s continuation. Every sham
matched the recorded nominal target position and velocity bit for bit after
restoring MuJoCo's full integration state. One assistance control was explicitly
unreachable under the no-assistance precondition, not resampled or omitted.

Removal changes collision permissions only between target and environment,
using an otherwise unused collision bit. All other geometry-pair mask
permissions are checked, including hand-environment interactions. Explicit
target pairs and heterogeneous target-hand permissions are rejected by this
adapter. The endpoint reads position, orientation and velocity, not the tested
no-load verdict. This is fixed recorded-action continuation, not controller
state recovery or an assertion of policy adaptation after an intervention.

One weak-clamp/floor case was dependent; six cases retained under both branches,
including a strong-clamp case with actual floor load. These are mechanism
engineering checks, not natural prevalence, a final accuracy estimate, or
evidence that the new method beats the strong complete-wrench baseline. Both
no-load methods agreed on this first debugging batch.

Recorded artifacts: `evidence/research_v4/calibration/development_controls_attempt_1/`
within this paper project. Subsequent attempts must use separate paths. Formal
numerical sensitivity and G1/G2 remain unfinished.

## Registered 48/80 Calibration

The 80-instance design was saved before outcomes in
`evidence/research_v4/calibration/free_controls_v1/design.json`. It includes
10 instances per mechanism, varied dimensions/mass/friction, three intentionally
weak independent holds, lateral offsets and rotational initial conditions.
The first 48 are a nested six-per-group subset. Source hashes were checked before
the remaining 32 ran. All 80 observer-off/on target trajectories were bit equal;
the separate raw reference agreed on every contract label and geometry/clock
check. This confirms this instrumentation chain, not external physical truth.

| Development Summary | First 48 | All 80 (Includes 48) |
| --- | --- | --- |
| B5 no-load PASS | 15 | 25 |
| B4 full-wrench PASS | 15 | 25 |
| No-contact PASS | 4 | 7 |
| Sham/removal both retain | 34 | 57 |
| Sham retains, removal fails | 6 | 10 |
| Unreachable under preconditions | 8 | 13 |
| Invalid sham restorations | 0 | 0 |

All eligible sham trajectories were bit equal. There were no both-fail or
removal-rescues cells among reached states; this limitation is reported rather
than filling cells synthetically. Default thresholds were used for these
development summaries. The final operating point, sensitivity checks, strongest
additional baselines, natural development branches, utility-route decision and
formal freeze are still pending. B5 and B4 made identical decisions on all 80:
there is no demonstrated incremental accuracy over the strong simple baseline.
