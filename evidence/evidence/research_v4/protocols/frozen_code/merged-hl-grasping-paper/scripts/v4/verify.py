"""Strictly read-only integrity checks; no rollout, download, or report rewrite."""
from .common import OUT, read_json, sha256


def run(require_complete=True):
    from .protocol import verify_lock
    protocol = verify_lock(check_runtime=False)
    verified, missing = [], []
    for source, directory in (('controls', OUT/'controls/final/cases'),
                              ('fetch', OUT/'external/fetch/final/cases'),
                              ('dexgraspbench', OUT/'external/dexgraspbench/final/cases')):
        rows = read_json(OUT/'protocols'/('final_'+source+'.json'))
        for row in rows:
            path = directory/(row['case_id']+'.json')
            if not path.exists():
                missing.append(str(path))
                continue
            record = read_json(path)
            if record['case'] != row or sha256(path.with_suffix('.npz')) != record['trace_sha256']:
                raise RuntimeError('Changed case or trace: '+str(path))
            verified.append(str(path))
    jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
    for job in jobs:
        jid = job['job_id']
        path = OUT/'external/allegro/final/scores'/(jid+'.json')
        if not path.exists():
            missing.append(str(path))
            continue
        record = read_json(path)
        raw = OUT/'external/allegro/final/raw'/(jid+'.json')
        if read_json(raw)['job'] != job or sha256(raw) != record['raw_metadata_sha256'] or sha256(raw.with_suffix('.npz')) != record['raw_sha256']:
            raise RuntimeError('Changed Allegro evidence: '+jid)
        verified.append(str(path))
    seal_path = OUT/'selection/u2_sealed.json'
    if seal_path.exists():
        sealed = read_json(seal_path)
        if sealed['protocol_sha256'] != sha256(OUT/'protocols/protocol_lock.json'):
            raise RuntimeError('Selection protocol changed')
        for jid, expected in sealed['score_hashes'].items():
            if sha256(OUT/'external/allegro/final/scores'/(jid+'.json')) != expected:
                raise RuntimeError('Sealed score changed')
            path = OUT/'selection/future'/(jid+'.json')
            if not path.exists():
                missing.append(str(path))
    elif require_complete:
        missing.append(str(seal_path))
    if require_complete and missing:
        raise RuntimeError(f'Incomplete evidence: {len(missing)} missing records; first={missing[0]}')
    return dict(status='PASS' if not missing else 'VALID_BUT_INCOMPLETE', cases_verified=len(verified),
                missing=len(missing), protocol_sha256=sha256(OUT/'protocols/protocol_lock.json'),
                side_effects='None: no physics, downloads, output writes or source changes')
