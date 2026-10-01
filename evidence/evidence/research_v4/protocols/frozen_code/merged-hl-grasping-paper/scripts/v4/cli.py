"""Version-specific research commands. No writes to historical evidence."""
from __future__ import annotations

import argparse
import json


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=("inventory", "verify-history", "retrospective", "doctor", "replay-one",
        "controls", "freeze", "external", "counterfactual", "select", "evaluate", "analyze", "verify", "package", "properties"))
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--limit-scenes", type=int)
    parser.add_argument("--fetch-smoke", action="store_true")
    parser.add_argument("--job-id")
    parser.add_argument("--replay-missing", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument('--split', choices=('calibration', 'final', 'smoke', 'validation'), default='final')
    parser.add_argument('--source', choices=('allegro', 'fetch', 'dexgraspbench'))
    parser.add_argument('--route', choices=('U1', 'U2'), default='U2')
    parser.add_argument('--protocol')
    parser.add_argument('--selection-lock')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--version', default='merged-v4')
    parser.add_argument('--out')
    args = parser.parse_args()
    if args.command == 'freeze':
        from .protocol import freeze
        result = freeze()
    elif args.command == 'controls':
        from .formal_controls import run
        result = run(args.split, args.workers)
    elif args.command == 'properties':
        from .formal_properties import run
        result = run()
    elif args.command == 'external':
        if args.source is None:
            parser.error('--source is required')
        if args.source == 'allegro':
            if args.split != 'final':
                parser.error('Allegro development uses replay-one, not a new smoke split')
            from .formal_allegro import run
            result = run(args.workers)
        else:
            from .formal_external import run
            result = run(args.source, args.workers, qualification=args.split == 'smoke')
    elif args.command == 'select':
        if args.route != 'U2':
            parser.error('U1 stopped at the genuine-pool development gate; no fabricated version comparison')
        from .formal_allegro import seal
        result = seal()
    elif args.command == 'evaluate':
        from pathlib import Path
        from .common import OUT
        if args.selection_lock and Path(args.selection_lock).resolve() != (OUT/'selection/u2_sealed.json').resolve():
            parser.error('Only the frozen U2 selection lock is accepted')
        from .formal_allegro import evaluate_future
        result = evaluate_future(args.workers)
    elif args.command == 'counterfactual':
        from pathlib import Path
        from .common import OUT, read_json
        from .protocol import verify_lock
        verify_lock(check_runtime=False)
        if args.protocol and Path(args.protocol).resolve() != (OUT/'protocols/protocol_lock.json').resolve():
            parser.error('Only the G2 protocol is accepted')
        result = dict(execution='Branches run with their source adapter and frozen nominal tapes; never reselect states',
                      branches=read_json(OUT/'protocols/protocol_lock.json')['branch'])
    elif args.command == 'analyze':
        from .formal_analysis import run
        report = run()
        result = {k: report[k] for k in ('confirmatory_gain_supported', 'utility_gain_supported', 'H1_B5_minus_B4')}
    elif args.command == 'verify':
        from .verify import run
        result = run()
    elif args.command == 'package':
        from .release import package
        result = package(args.version, args.out)
    elif args.command == "replay-one":
        from .adapters.allegro import replay_one
        result = replay_one(args.job_id)
    elif args.command == "doctor":
        from . import doctor
        result = doctor.run(args.fetch_smoke)
    elif args.command == "retrospective":
        if args.replay_missing:
            from . import replay_missing
            result = replay_missing.run(args.workers)
        else:
            from . import retrospective
            result = retrospective.run(args.limit_scenes)
    else:
        from . import inventory
        result = inventory.run() if args.command == "inventory" else inventory.verify_protection()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
