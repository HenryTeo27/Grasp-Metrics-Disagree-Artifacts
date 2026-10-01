# Frozen Program And Candidate Differences

Source: V3 `jobs.json` + `membership.json`; executable extraction:
`python -B -m scripts.v4.cli inventory` from the merged-paper root.
Detailed rows: `evidence/research_v4/manifests/candidate_registry.csv` and
`candidate_budget.csv`.

- Three named conditions have 6,480 logical candidate slots on 360 scenes,
  sharing 2,278 unique physics executions. There are no within-scene duplicate
  slots in baseline, repair, or No-extra. Caching across conditions is not an
  additional independent observation.
- Baseline has 29 distinct candidate specifications; repair has 35; No-extra
  has the same 29 as baseline. Candidate identity includes runner, anchor,
  derived-control offsets, extension duration, and native thresholds.
- Ordered baseline/repair candidates are identical in every cube, cylinder,
  bar, capsule and flat-box scene. They differ in 46/60 sphere scenes and are
  identical in the other 14. No-extra equals baseline in all 360 scenes.
- Staged candidates use a fixed six-anchor order. Hold-selector candidates
  rank the frozen library by initial target XY distance and use its first six.
  The additional sphere anchors change that ordered neighborhood; they do not
  apply an across-family runtime repair. K=1 and K=3 are ordered K=6 prefixes.
- The native selector ranks executed candidates using recorded outcomes.
  It is not a prospective perception-to-action policy. Coverage and selected
  outcomes coincide in this archived dataset; this does not establish utility.
- Complete phase parameters live in each hash-locked anchor JSON. The schedule
  reconstruction in `scripts/v4/adapters/allegro.py` accounts for settling,
  approach/contact, grip, optional micro/bridge/cradle/feedback phases, lift,
  support ramp and terminal hold. It predicts all 3,087 archived final counters
  exactly, without reading those counters to choose the schedule.

The previous suggestion that No-extra might repeat candidates to fill its
budget was a question, not a finding. The extraction resolves it negatively.
