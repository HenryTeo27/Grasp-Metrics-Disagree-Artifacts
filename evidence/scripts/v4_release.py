"""Compact label-level V4 release, separate from the full local raw archive."""
from pathlib import Path
import argparse
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.common import OUT, read_json, sha256


def package(version='merged-v4', destination=None):
    if version != 'merged-v4' or not destination:
        raise ValueError('Use --version merged-v4 and an explicit new --out directory')
    from scripts.v4.verify import run
    integrity = run()
    target = Path(destination).resolve()
    if target.exists():
        raise FileExistsError('Release directory must be new: '+str(target))
    target.mkdir(parents=True)
    paths = set()
    def include(base, pattern):
        paths.update(p for p in (ROOT/base).glob(pattern) if p.is_file() and '__pycache__' not in p.parts)
    include('scripts/v4', '**/*.py')
    include('tests/v4', '*.py')
    include('reproduce_v4', '*')
    include('notes/v4', '*')
    for name in ('v4_figures.py', 'v4_publication.py', 'v4_historical_appendix.py', 'v4_execution_recovery.py', 'v4_dynamic_release_check.py', 'v4_release.py', 'v4_release_audit.py', 'v4_source_release.py', 'v4_pdf_qa.py'):
        paths.add(ROOT/'scripts'/name)
    paths.add(ROOT/'README_V4.md')
    for base in ('analysis', 'protocols', 'manifests', 'reports', 'controls', 'external', 'selection', 'retrospective', 'calibration'):
        for suffix in ('*.json', '*.csv', '*.md'):
            include('evidence/research_v4/'+base, '**/'+suffix)
    include('evidence/research_v4', '*.csv')
    include('evidence/research_v4', '*.md')
    include('evidence/research_v4/protocols', '**/*.py')
    for name in ('case_results.csv', 'analysis.json', 'cases.json', 'physics_sensitivity.csv', 'protocol.json', 'suite_lock.json'):
        paths.add(ROOT/'evidence/prospective_v3'/name)
    # Only the three original primitive control models have model_xml payloads.
    # External metadata contains derived measurements, not upstream meshes/code.
    for cid in ('final_control_000', 'final_control_001', 'final_control_002'):
        paths.add(OUT/'controls/final/cases'/(cid+'.npz'))
    include('paper_v4/figures/render_arrays', '*.npy')
    include('paper_v4/figures/render_arrays', '*.json')
    include('paper_v4', '*.tex')
    include('paper_v4', '*.bib')
    include('paper_v4/sections', '*.tex')
    include('paper_v4/generated', '*.tex')
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        output = target/relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, output)
    # Package summaries are not allowed to silently redefine the original frozen code.
    lock = read_json(OUT/'protocols/protocol_lock.json')
    frozen = {}
    for relative, value in lock['code_hashes'].items():
        prefix = ROOT.name+'/'
        if relative.startswith(prefix) and (target/relative[len(prefix):]).exists():
            local = relative[len(prefix):]
            if sha256(target/local) != value:
                raise RuntimeError('Frozen packaged file changed: '+local)
            frozen[local] = value
    raw = []
    raw_paths = [path for directory in ('calibration', 'controls', 'external', 'retrospective', 'reports/dynamic_release')
                 for path in (OUT/directory).rglob('*.npz')]
    for path in sorted(raw_paths):
        relative = path.relative_to(ROOT).as_posix()
        raw.append(dict(path=relative, bytes=path.stat().st_size, sha256=sha256(path), included=(target/relative).exists()))
    def write(name, value):
        (target/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    write('raw_trace_manifest.json', dict(scope='Full locally retained raw inventory; only included=true entries distributed', files=raw))
    write('packaging.json', dict(version=version, integrity=integrity, packaged_frozen_code=frozen,
        full_raw_trace_bytes=sum(r['bytes'] for r in raw), raw_files_bundled=sum(r['included'] for r in raw),
        third_party_assets='Excluded; no silent download or substitution', full_dynamic_reproduction='NOT_CLAIMED'))
    shutil.copy2(ROOT/'reproduce_v4/README.md', target/'README.md')
    shutil.copy2(ROOT/'reproduce_v4/dependencies.md', target/'dependencies.md')
    manifest = ''.join(sha256(p)+'  '+p.relative_to(target).as_posix()+'\n' for p in sorted(target.rglob('*')) if p.is_file())
    (target/'MANIFEST.sha256').write_text(manifest, encoding='utf-8')
    return dict(status='PACKAGED_NOT_YET_REPRODUCED', directory=str(target), files=len(manifest.splitlines()),
                raw_inventory=len(raw), full_local_raw_bytes=sum(r['bytes'] for r in raw))


def archive(directory, path):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for source in sorted(Path(directory).rglob('*')):
            if source.is_file():
                z.write(source, source.relative_to(directory))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--version', default='merged-v4')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.version, args.out), indent=2))
