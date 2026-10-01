# Telemetry Gap And Additive Replay

The frozen V3 schema has **18**, not 17, telemetry columns. The integrated plan's
column count was an off-by-one documentation error. Field names, not positional
guesses, drive the new analysis.

V3 provides summed environmental normal force, net world force, contact distance,
primitive floor clearance, COM/attitude, region normal forces and contact counts.
It lacks per-contact points, contact frames, tangential forces, torque, and true
constraint activation. Its `environment_active_count` is a force-threshold count,
not `efc_address >= 0`. Net force cannot reveal cancelling environmental loads.

P1 inspected all six candidates for the union of 85 excluded scenes, retaining
510 unique jobs, 1,530 program/rank memberships and 5,007 local-Q intervals.
Both programs exclude the same 85 scenes. Of 510 candidates, 177 satisfy global
Q and have at least 15 seconds of local Q; 333 already fail those unchanged
conditions. Two scenes have no candidate satisfying this complete common gate.
The 177 eligible candidates all show sustained upward environment load under
the old diagnostic threshold. This does not prove necessary dependence or
exclude a separate 15-second low-load interval.

Full additive replays were therefore assigned to all 177 potentially relevant
candidates, while every other candidate stays in the accounting with its common
condition failure. All 177 replays matched original samples, legacy telemetry,
timestamps, native metrics and temporal metrics exactly. The fixed anchor
schedule also matched every final counter. Runtime: 451.36 s with four workers;
new compressed traces: 2,887,068,455 bytes. These are additional measurements of
old cases, not 177 new independent scenes or a fresh test.

The new recorder stores full contact wrenches about target COM, both absolute
and net aggregation, true active constraints, pre-solve free-joint velocity,
explicit applied-force flags, target edits, actuator commands/forces, a fixed
8-second integration-state snapshot, and separately named post-step states.
It makes no additional `mj_forward` or integration call. Eleven physical unit
tests cover force direction, cancellation, torsion, sampling consistency,
observer equality, assistance, edits, scale and state extraction.

The geometric/environmental adjudication and the calibrated C_NL verdict are
subsequent P2 work. No V3 score has been replaced.
