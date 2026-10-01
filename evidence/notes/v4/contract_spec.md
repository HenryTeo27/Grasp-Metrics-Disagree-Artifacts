# Frozen Contract Specification

The machine-readable authority is `evidence/research_v4/protocols/protocol_lock.json`.
This note explains the pre-test design; it does not change it.

## Signals and Outputs

Every observed contact solve records the local six-dimensional contact wrench,
frame, application point, active constraint address, role, target COM, free-joint
state and timestep. World moments are about the target COM. External contact
load is the sum of individual wrench magnitudes, not the norm of their sum.
Known target free-joint damping is separately metered using the larger of the
solve-state and implicit endpoint magnitudes. An unexplained passive residual
or unsupported force path remains indeterminate.

Let F be external force divided by mg and M external moment divided by mgL,
with L the object half-diagonal (declared compound bounding box for DGB).
The lower bound is 1e-4 and upper bound 1e-2 for both F and M. A continuous
15-second interval must satisfy the source-specific common task conditions Q.
Geometry tolerance is 1e-5 m. Clear separation can disambiguate inactive contact
records; an active zero-load constraint is not silently treated as known safe.
Fetch uses conservative enclosing boxes where exact mesh distance is unavailable.

PASS requires a definite interval. FAIL means even the possible interval is too
short. Otherwise the verdict is INDETERMINATE. Invalid telemetry has a separate
validity field; invalid and indeterminate are not physical failure labels.
The literal no-contact contract counts all generated environmental records,
including inactive records, with the same Q and duration.

## Branches and Uses

Counterfactual branches restore the complete `mjSTATE_INTEGRATION` state.
The sham uses the same model and command tape. It must reproduce the original
target position and velocity trajectory bit-for-bit. The removal branch changes
only target-environment collision permission. The all-sample endpoint bounds
are displacement 0.03 m, angle 0.35 rad and speed 0.2 m/s over H=3 seconds.
Natural endpoints use the current palm frame; controlled pads use world frame.
This is dependence under a specified intervention and continuation, not a
general causal necessity or physical support theorem.

U2 observes the same complete K-prefix schedules for every method. It selects
the first PASS, otherwise abstains. Choices and score hashes are sealed before
the added 15-second future outcomes. That separate use holds final commands and
mocap fixed, removes target-environment contact permission and applies the
same palm-relative endpoint bounds. All 720 futures are evaluated to expose
finite-pool regret, but the independent decision count remains 120 scenes.

## Risk and Statistical Interpretation

The 5% empirical accepted-risk ceiling is a measurement-benchmark criterion,
not a deployment safety certificate. The 5 percentage-point practical effect
threshold is a pre-test resource/value decision, not an effect inferred from
test data. Two primary B5-B4 comparisons use 97.5% two-sided paired bootstrap
intervals; descriptive intervals are 95%. Small counts, same-apparatus
dependence and four DGB identities limit the precision of all generalization
claims. Observed equality is not population equivalence.
