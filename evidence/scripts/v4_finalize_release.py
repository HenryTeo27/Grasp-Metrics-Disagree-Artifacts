"""Finalize checksums only after testing an independently extracted evidence ZIP."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v4.common import OUT, read_json, sha256
from scripts.v4_release import archive

OFFLINE_PYTHON = Path('C:/Users/User/.cache/codex-dexgraspbench-venv/Scripts/python.exe')


def run():
    stage = ROOT/'build_v4/evidence_final'
    dist, stem = ROOT/'dist', 'merged_hl_grasping_paper_v4'
    evidence_zip = dist/(stem+'_evidence.zip')
    extracted = ROOT/'build_v4/evidence_zip_check'
    recomputed = ROOT/'build_v4/evidence_zip_recomputed'
    source = read_json(ROOT/'build_v4/source_verification.json')
    audit = read_json(OUT/'reports/release_audit.json')
    assert source['status'] == audit['status'] == 'PASS'
    with zipfile.ZipFile(dist/(stem+'_latex_source.zip')) as z:
        for name in z.namelist():
            assert z.read(name) == (ROOT/'paper_v4'/name).read_bytes(), 'Source changed after isolated build: '+name
    if evidence_zip.exists() or extracted.exists() or recomputed.exists():
        raise FileExistsError('Final extraction/archive destinations must be new')
    # These are release prose, never the original locked experimental inputs.
    for name in ('execution_log.md', 'completion_audit.md', 'reviewer_response_matrix.md', 'submission_readiness.md'):
        shutil.copy2(ROOT/'notes/v4'/name, stage/'notes/v4'/name)
    shutil.copy2(Path(__file__), stage/'scripts/v4_finalize_release.py')
    manifest = ''.join(sha256(p)+'  '+p.relative_to(stage).as_posix()+'\n'
        for p in sorted(stage.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256')
    (stage/'MANIFEST.sha256').write_text(manifest, encoding='utf-8')
    archive(stage, evidence_zip)
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(evidence_zip) as z:
        assert z.testzip() is None
        for name in z.namelist():
            if not (extracted/name).resolve().is_relative_to(extracted):
                raise RuntimeError('Unsafe ZIP entry')
        z.extractall(extracted)
    command = [str(OFFLINE_PYTHON), '-B', str(extracted/'reproduce_v4/reproduce.py'), '--out', str(recomputed)]
    check = subprocess.run(command, cwd=extracted, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (ROOT/'build_v4/evidence_zip_check_output.txt').write_text(check.stdout+'\n'+check.stderr, encoding='utf-8')
    if check.returncode:
        raise RuntimeError(check.stderr[-6000:])
    offline = read_json(recomputed/'verification.json')
    assert offline['status'] == 'PASS'
    dynamic = {s: read_json(OUT/'reports/dynamic_release'/s/'verification.json') for s in ('controls', 'allegro', 'fetch', 'dexgraspbench')}
    assert all(r['status'] == 'PASS' for r in dynamic.values())
    files = [dist/(stem+'.pdf'), dist/(stem+'_latex_source.zip'), evidence_zip]
    verification = dict(version='merged-v4', status='PASS_WITH_DECLARED_SCOPE_LIMITATIONS',
        source_build=source, offline_extracted_evidence=offline,
        historical_protection=audit['historical_protection'], frozen_v3=audit['frozen_v3'],
        qualification_tests=audit['frozen_unit_tests'], negative_controls=audit['negative_tests'],
        figures_pixel_equal=audit['regenerated_figure_pixels_equal'], pdf_visual_review=audit['manuscript_visual_review'],
        dynamic_fixed_cases=dynamic, formal_integrity=read_json(stage/'packaging.json')['integrity'],
        no_new_method_gain_demonstrated=True,
        unsupported=['Independent learned acquisition controller', 'Human-blinded reference labeling',
            'Hardware or second physics engine', 'Complete publicly downloadable raw traces',
            'Independent clean-machine or full-matrix dynamic reproduction', 'Venue-specific submission compliance'],
        outputs={p.name: dict(bytes=p.stat().st_size, sha256=sha256(p)) for p in files})
    destination = dist/(stem+'_verification.json')
    destination.write_text(json.dumps(verification, indent=2)+'\n', encoding='utf-8')
    files.append(destination)
    sums = ''.join(sha256(p)+'  '+p.name+'\n' for p in files)
    (dist/(stem+'_SHA256SUMS.txt')).write_text(sums, encoding='utf-8')
    return dict(status=verification['status'], pages=source['pages'], offline=offline['status'],
        outputs={p.name: p.stat().st_size for p in files}, unsupported=verification['unsupported'])


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
