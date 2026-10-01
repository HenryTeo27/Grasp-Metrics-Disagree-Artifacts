# V4 Novelty Gate and Claim Registry

Recorded before formal G2 outcomes. Status: diagnostic/measurement study admitted;
algorithm-superiority and broad-policy-generalization claims are not presumed.

## Closest Work

| Primary source | Existing contribution | Boundary of this study |
| --- | --- | --- |
| [SafeManip v3](https://arxiv.org/html/2605.12386v3) | Temporal manipulation safety properties and cross-environment monitoring | We do not claim new temporal logic or novelty from reusable monitoring. We isolate contact representation, realized external load, and intervention-conditioned retention in one instrumented physical setting. |
| [Get a Grip](https://proceedings.mlr.press/v270/lum25b.html) | Learned multi-finger grasp evaluation for selection and refinement, including real-world transfer | Selection using an evaluator is established. Our U2 test asks whether a specific added geometry guard provides incremental utility over a strong wrench monitor; no new learned evaluator or real-world result is claimed. |
| [Task-Oriented Dexterous Hand Pose Synthesis](https://arxiv.org/abs/2309.13586) | Matching task wrench requirements to achievable grasp wrenches | The B6 linear program is a deliberately approximate mechanical baseline, not a new wrench theory or truth label for realized behavior. |
| [Grasp to Act](https://arxiv.org/html/2602.20466v1) | Perturbation-based grasp assessment for dynamic tool use | Signed-force probes and downstream evaluation are not new. The present intervention holds the command tape fixed and changes only target-environment permission, with the full-state sham required to match. |
| [DexGraspBench](https://github.com/JYChen18/DexGraspBench) | Multi-hand grasp stability evaluation | We preserve its native signed-force task and separately add gravity retention to exposed static pose records. Neither its published aggregate performance nor learned tabletop acquisition is reproduced. |

This is a distinction table, not a claim that the literature has no other related
work. Source contents were checked from the primary pages on 2026-10-01.

## Development Decisions

- Instrument qualification: all 80 registered controls have identical complete
  integration-state traces with observation on/off. Source-specific external
  qualifications and an independently coded raw-wrench/geometry reconstruction
  are recorded separately.
- No two independent human or agent annotators are available. The implementer
  runs all code. Hashes, timestamps, input-only manifests and selection sealing
  support procedural accountability, not blind human ground truth.
- B4 and B5 agree throughout the development evidence. A simple geometry-only
  baseline also agrees on the 80 controls. This prevents treating the integration
  work as an established algorithmic advantage.
- The 85 historical scene exclusions are not rescued by the new no-load
  contract. The 177 fully measured candidates fail; 333 candidates already fail
  unchanged common conditions. Their unmeasured load is not imputed.
- A natural 20-scene development subset contains three loaded states retaining
  after a short removal, but a simple pre-branch load threshold separates this
  small biased subset. No new dependency-prediction model is promoted.
- U1 stops: only two authentic versions exist and all examined scores promote
  the same repair. U2 is admitted because the original six-candidate pool gives
  nonidentical acceptance decisions, not because B5 has already beaten B4.
- The unavailable native robomimic runtime is not replaced by a claimed learned
  controller. DGB is a static library portability test with four held-out object
  identities and a different pinned MuJoCo version, not a new physics engine.

## Claim Registry

| ID | Proposed statement | Evidence needed | Gate |
| --- | --- | --- | --- |
| C1 | No-contact, realized no-load, and short intervention dependence are different constructs | Registered physical controls, raw reference, paired shams and retained native semantics | Diagnostic claim; no universal contact prohibition |
| C2 | B5 improves correct acceptance over B4 under the registered risk rule | H1 paired formal controls, multiplicity-adjusted interval and practical effect threshold | Unsupported until frozen test; negative outcome publishable |
| C3 | B5 improves usable candidate decisions over B4 | Sealed K6 U2 choices followed by independent added 15s retention | Unsupported until frozen test; abstentions remain in N |
| C4 | Instrument can be adapted to these sources | Per-source qualifications, roles, task contracts, missing/unknown accounting | Limited adapter portability; no arbitrary policy generalization |
| C5 | Historical 85 exclusions were false negatives of no-contact | All-candidate retrospective adjudication | Rejected on development evidence; 0/85 rescued |
| C6 | A new dependency predictor is necessary | Stable natural labels and advantage over pre-branch simple rules | Stopped; development does not justify it |
| C7 | Robust dexterous grasping, real-world safety or RL replacement | Substantially different experiments | Prohibited |

The paper should be framed as a falsifiable measurement and negative-result
study if C2/C3 remain unsupported. Completion of the planned engineering does
not imply a competitive full-method-paper contribution.
