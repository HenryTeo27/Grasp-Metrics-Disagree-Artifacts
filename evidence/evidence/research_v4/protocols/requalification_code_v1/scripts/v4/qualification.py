"""Persist unit-test provenance without modifying physics or historical inputs."""
from pathlib import Path
import re
import subprocess
import sys

from .common import OUT, PAPER, sha256, utc_now, write_json


def run():
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests/v4', '-v'],
                            cwd=PAPER, capture_output=True, text=True, encoding='utf-8')
    output = result.stdout+result.stderr
    match = re.search(r'Ran (\d+) tests', output)
    record = dict(created_utc=utc_now(), executable=sys.executable, exit_code=result.returncode,
                  passed=result.returncode == 0, tests=int(match.group(1)) if match else None,
                  source_hashes={p.relative_to(PAPER).as_posix(): sha256(p)
                                 for root in (PAPER/'scripts/v4', PAPER/'tests/v4') for p in sorted(root.rglob('*.py'))},
                  output=output)
    write_json(OUT/'calibration/unit_test_qualification_v1.json', record, exclusive=True)
    print(output[-2500:])
    if result.returncode:
        raise RuntimeError('V4 unit tests failed')
    return record


if __name__ == '__main__':
    run()
