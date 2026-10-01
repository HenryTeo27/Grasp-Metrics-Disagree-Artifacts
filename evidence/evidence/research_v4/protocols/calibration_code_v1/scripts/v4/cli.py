"""Version-specific research commands. No writes to historical evidence."""
from __future__ import annotations

import argparse
import json


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=("inventory", "verify-history", "retrospective", "doctor", "replay-one"))
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--limit-scenes", type=int)
    parser.add_argument("--fetch-smoke", action="store_true")
    parser.add_argument("--job-id")
    parser.add_argument("--replay-missing", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.command == "replay-one":
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
