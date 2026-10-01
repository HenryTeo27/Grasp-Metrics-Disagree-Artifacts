"""Fresh frozen-candidate runs, then sealed U2 choices, then future-use outcomes."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json
import time

import mujoco
import numpy as np

from .adapters.allegro import execute, frozen
from .baselines import historical, verdict
from .common import OUT, read_json, sha256, utc_now, write_json
from .contracts import Calibration
from .counterfactual import branch_model
from .external_reference import adjudicate
from .mechanical_baselines import signed_force_probe, static_feasibility
from .natural_pilot import adapt
from .selection import accept_first, future_retention

BASE = OUT/'external/allegro/final'
METHODS = ('B0', 'B1', 'B2', 'B3', 'B4', 'B4_normal', 'B5')


def factory_for(case):
    def factory():
        model, _ = frozen.compile_case(frozen.old.SCENE, case)
        frozen.old.apply_object_geom(model, case)
        return model
    return factory


def prepare(arrays, meta):
    metadata, gap = adapt(arrays, meta)
    arrays['geometry_gap'] = gap
    model = factory_for(meta['job']['case'])()
    gid = model.geom('object').id
    names = {mujoco.mjtGeom.mjGEOM_BOX: 'box', mujoco.mjtGeom.mjGEOM_SPHERE: 'sphere',
             mujoco.mjtGeom.mjGEOM_CYLINDER: 'cylinder', mujoco.mjtGeom.mjGEOM_CAPSULE: 'capsule'}
    metadata['allegro_reference'] = dict(shape=names[model.geom_type[gid]], size=model.geom_size[gid].tolist(),
        floor_z=float(model.geom_pos[model.geom('floor').id, 2]), settle_steps=meta['result']['settle_steps'],
        min_lift_m=meta['job']['candidate']['thresholds']['min_lift_m'],
        palm_opposition=meta['job']['candidate']['runner'] == 'hold')
    return metadata


def one(request):
    job, config = request
    raw = BASE/'raw'
    jid = job['job_id']
    if not (raw/(jid+'.json')).exists():
        execute(job, raw, snapshot_time='late')
    meta = read_json(raw/(jid+'.json'))
    if sha256(raw/(jid+'.npz')) != meta['trace_sha256']:
        raise RuntimeError('Raw trace changed')
    with np.load(raw/(jid+'.npz'), allow_pickle=False) as z:
        arrays = dict(z)
    metadata = prepare(arrays, meta)
    methods = historical(arrays, metadata, config)
    methods['B0'] = dict(verdict='PASS' if meta['result']['legacy_success'] else 'FAIL', trace_validity='VALID',
                         scope='Actual unchanged native legacy gate, not the generic accumulated-Q proxy')
    factory = factory_for(job['case'])
    cf = branch_model(arrays, metadata, factory) if job['counterfactual_selected'] else dict(status='NOT_SELECTED')
    b6 = static_feasibility(arrays, metadata, factory) if job['counterfactual_selected'] else dict(status='NOT_SELECTED')
    b7 = signed_force_probe(arrays, metadata, factory) if job['counterfactual_selected'] else dict(status='NOT_SELECTED')
    reference = adjudicate(arrays, metadata) if job['reference_selected'] else dict(verdict='NOT_SELECTED')
    result = dict(job_id=jid, case_id=job['case']['case_id'], family=job['family'], rank=job['rank'],
                  methods=methods, reference=reference, counterfactual=cf, B6=b6, B7=b7,
                  raw_sha256=meta['trace_sha256'], raw_metadata_sha256=sha256(raw/(jid+'.json')),
                  nominal_physics_steps=meta['planned_steps'], elapsed_s=meta['elapsed_s'],
                  branch_cost_steps=(2*round(3/meta['result']['dt']) if cf['status'] == 'VALID' else 0)+b7.get('physics_steps', 0))
    write_json(BASE/'scores'/(jid+'.json'), result, exclusive=True)
    return dict(job_id=jid, B0=verdict(methods['B0']), B4=verdict(methods['B4']), B5=verdict(methods['B5']))


def run(workers=4):
    from .protocol import verify_lock
    lock = verify_lock()
    jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
    todo = [(j, Calibration(**lock['calibration'])) for j in jobs if not (BASE/'scores'/(j['job_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(one, todo):
            print(json.dumps(result), flush=True)
    return dict(candidates=len(jobs), scenes=len({j['case']['case_id'] for j in jobs}), remaining=0)


def seal():
    from .protocol import verify_lock
    verify_lock()
    target = OUT/'selection/u2_sealed.json'
    if target.exists():
        raise FileExistsError('Selection already sealed')
    if any((OUT/'selection/future').glob('*.json')):
        raise RuntimeError('Future outcomes were opened before selection seal')
    jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
    results, hashes, scenes = {}, {}, {}
    for job in jobs:
        jid, case = job['job_id'], job['case']['case_id']
        path = BASE/'scores'/(jid+'.json')
        record = read_json(path)
        results[jid] = {k: verdict(record['methods'][k]) for k in METHODS}
        hashes[jid] = sha256(path)
        scenes.setdefault(case, []).append(job)
    choices = []
    for case, scene_jobs in sorted(scenes.items()):
        ordered = [j['job_id'] for j in sorted(scene_jobs, key=lambda j: j['rank'])]
        for k in (1, 3, 6):
            for method in METHODS:
                choices.append(dict(case_id=case, family=scene_jobs[0]['family'], k=k, method=method,
                    selected_job=accept_first(ordered, results, method, k),
                    candidate_pool=ordered[:k],
                    budget_physics_steps=sum(read_json(BASE/'scores'/(jid+'.json'))['nominal_physics_steps'] for jid in ordered[:k])))
    payload = dict(sealed_utc=utc_now(), role='U2 predictions sealed before any future-use outcomes',
                   protocol_sha256=sha256(OUT/'protocols/protocol_lock.json'), score_hashes=hashes, choices=choices,
                   selection='First PASS in frozen rank order within K, otherwise abstain; all K full schedules charged')
    write_json(target, payload, exclusive=True)
    return dict(choices=len(choices), scenes=len(scenes), sealed_utc=payload['sealed_utc'])


def future_one(job):
    raw = BASE/'raw'
    jid = job['job_id']
    meta = read_json(raw/(jid+'.json'))
    with np.load(raw/(jid+'.npz'), allow_pickle=False) as z:
        arrays = dict(z)
    metadata = prepare(arrays, meta)
    started = time.perf_counter()
    result = future_retention(arrays['final_integration_state'], meta['final_state_flag'], metadata, factory_for(job['case']))
    write_json(OUT/'selection/future'/(jid+'.json'), dict(job_id=jid, case_id=job['case']['case_id'],
        outcome=result, elapsed_s=time.perf_counter()-started), exclusive=True)
    return dict(job_id=jid, **result)


def evaluate_future(workers=4):
    from .protocol import verify_lock
    verify_lock()
    sealed = read_json(OUT/'selection/u2_sealed.json')
    if sealed['protocol_sha256'] != sha256(OUT/'protocols/protocol_lock.json'):
        raise RuntimeError('Protocol changed after sealing')
    for jid, expected in sealed['score_hashes'].items():
        if sha256(BASE/'scores'/(jid+'.json')) != expected:
            raise RuntimeError('Sealed score changed')
        score = read_json(BASE/'scores'/(jid+'.json'))
        if sha256(BASE/'raw'/(jid+'.json')) != score['raw_metadata_sha256'] or sha256(BASE/'raw'/(jid+'.npz')) != score['raw_sha256']:
            raise RuntimeError('Sealed input changed')
    jobs = read_json(OUT/'protocols/final_allegro_jobs.json')
    todo = [j for j in jobs if not (OUT/'selection/future'/(j['job_id']+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(future_one, todo):
            print(json.dumps(result), flush=True)
    return dict(outcomes=len(jobs), role='All fixed candidates scored; not new independent scenes')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'select', 'evaluate'))
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    print({'run': run, 'select': lambda **_: seal(), 'evaluate': evaluate_future}[args.action](workers=args.workers))
