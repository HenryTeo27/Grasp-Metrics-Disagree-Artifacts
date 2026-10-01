"""Release-only tests; frozen experimental code remains unmodified."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.common import OUT, read_json, sha256, write_json
from scripts.v4.inventory import verify_protection, frozen_inputs, recount


def run():
    spec = importlib.util.spec_from_file_location('offline_verify', ROOT/'reproduce_v4/reproduce.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    negative_tests = []
    with tempfile.TemporaryDirectory(prefix='v4-manifest-check-') as directory:
        root = Path(directory)
        module.ROOT = root
        value = root/'sample.json'
        value.write_text('{"valid":true}\n', encoding='utf-8')
        (root/'MANIFEST.sha256').write_text(sha256(value)+'  sample.json\n', encoding='utf-8')
        assert module.verify_manifest() == 1
        value.write_text('{"valid":false}\n', encoding='utf-8')
        try:
            module.verify_manifest()
        except RuntimeError:
            negative_tests.append('tampered input rejected')
        else:
            raise AssertionError('Tampered input passed')
        (root/'MANIFEST.sha256').write_text('0'*64+'  ../outside.json\n', encoding='utf-8')
        try:
            module.verify_manifest()
        except RuntimeError:
            negative_tests.append('path escape rejected')
        else:
            raise AssertionError('Path escape passed')
    tests = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests/v4', '-p', 'test_*.py'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    log = tests.stdout+'\n'+tests.stderr
    (OUT/'reports/release_unit_tests.log').write_text(log, encoding='utf-8')
    if tests.returncode:
        raise RuntimeError(log[-5000:])
    protection = verify_protection()
    historical = recount()
    figures = {}
    for name in ('contract_examples', 'experimental_contrasts', 'risk_coverage_utility'):
        figures[name] = sha256(ROOT/'paper_v4/figures'/(name+'.png')) == sha256(ROOT/'build_v4/reproduced_stage_1/figures'/(name+'.png'))
    assert all(figures.values())
    result = dict(status='PASS', negative_tests=negative_tests, frozen_unit_tests=log[-600:],
        historical_protection={k: v for k, v in protection.items() if k != 'authorized_archived_files'},
        authorized_archived_files=len(protection['authorized_archived_files']), frozen_v3=frozen_inputs(),
        historical_recount=historical, regenerated_figure_pixels_equal=figures,
        manuscript_visual_review='All 12 pages contact sheet; detailed pages 6 and 11 plus all three standalone figures; no clipping/overlap found',
        caveat='Same-workflow release audit, not independent human review')
    write_json(OUT/'reports/release_audit.json', result)
    return dict(status=result['status'], negative_tests=negative_tests, historical=protection['protection'], figures=figures)


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
