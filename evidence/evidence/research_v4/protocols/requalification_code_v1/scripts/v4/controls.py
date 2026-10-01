"""Development controls: a free object, two actuated pads, and explicit environment."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import time

import mujoco
import numpy as np

from .common import OUT, fingerprint, output_path, write_json
from .contact_observer import ContactRecorder, ROLE_ENV, ROLE_THUMB, ROLE_OPPOSING
from .contracts import Calibration, evaluate

MECHANISMS = ("independent", "inactive_margin", "necessary_floor", "redundant_floor",
              "opposing_environment", "intermittent_floor", "applied_assistance", "boundary_gap")


@dataclass(frozen=True)
class Fixture:
    mechanism: str
    seed: int
    mass: float = .075
    half_x: float = .030
    half_y: float = .025
    half_z: float = .030
    pad_friction: float = .8
    duration_s: float = 18.
    timestep_s: float = .002
    jaw_command: float = .012
    gap_m: float = .010
    target_tilt_rad: float = 0.
    target_offset_y: float = 0.
    initial_angular_speed: float = 0.
    solver_iterations: int = 100
    solver_tolerance: float = 1e-10
    support_schedule: str = 'periodic'

    @property
    def signature(self):
        return fingerprint(asdict(self))


def build(fixture):
    p = fixture
    if p.mechanism not in MECHANISMS:
        raise ValueError(p.mechanism)
    floor = .5 - p.half_z
    planes = [('base_floor', '0 0 .02', '1 0 0 0', '0', '0')]
    if p.mechanism in ("necessary_floor", "redundant_floor", "intermittent_floor"):
        planes.append(('support', f'0 0 {floor+.00015}', '1 0 0 0', '0', '0'))
    elif p.mechanism in ("inactive_margin", "boundary_gap"):
        gap = p.gap_m if p.mechanism == "inactive_margin" else p.gap_m*.7
        planes.append(('support', f'0 0 {floor-gap}', '1 0 0 0', '.020', '.020'))
    elif p.mechanism == "opposing_environment":
        planes.extend([
            ('side_a', f'0 {-p.half_y+.00015} .5', '.7071067811865476 -.7071067811865476 0 0', '0', '0'),
            ('side_b', f'0 {p.half_y-.00015} .5', '.7071067811865476 .7071067811865476 0 0', '0', '0')])
    env = ''.join(f'<body name="env_{name}" mocap="true" pos="{pos}" quat="{quat}">'
                  f'<geom name="{name}" type="plane" size="1 1 .01" contype="2" conaffinity="4" '
                  f'friction=".8 .005 .0001" margin="{margin}" gap="{gap}"/></body>'
                  for name, pos, quat, margin, gap in planes)
    pads = ''.join(
        f'<body name="pad_{name}" pos="{sign*(p.half_x+.015+.003)} 0 .5">'
        f'<joint name="{name}" type="slide" axis="{-sign} 0 0" damping="2"/>'
        f'<geom name="pad_geom_{name}" type="box" size=".015 .045 .045" mass=".2" '
        f'contype="1" conaffinity="4" friction="{p.pad_friction} .005 .0001"/></body>'
        for name, sign in (("left", -1), ("right", 1)))
    xml = (f'<mujoco model="free_target_development_control"><option timestep="{p.timestep_s}" '
           f'gravity="0 0 -9.81" integrator="implicitfast" cone="elliptic" iterations="{p.solver_iterations}" tolerance="{p.solver_tolerance}"/>'
           '<default><geom condim="6" solref=".01 1" solimp=".95 .99 .001"/></default>'
           f'<worldbody>{env}{pads}<body name="target" pos="0 {p.target_offset_y} .5" '
           f'quat="{np.cos(p.target_tilt_rad/2)} {np.sin(p.target_tilt_rad/2)} 0 0"><freejoint name="target_free"/>'
           f'<geom name="object" type="box" size="{p.half_x} {p.half_y} {p.half_z}" '
           f'mass="{p.mass}" contype="4" conaffinity="3" friction=".8 .005 .0001"/>'
           '</body></worldbody><actuator><position joint="left" kp="1000" forcelimited="true" '
           'forcerange="-20 20"/><position joint="right" kp="1000" forcelimited="true" '
           'forcerange="-20 20"/></actuator></mujoco>')
    model = mujoco.MjModel.from_xml_string(xml)
    return model, xml


def run_fixture(fixture, *, record=True, verify_full_state=False):
    model, xml = build(fixture)
    data = mujoco.MjData(model)
    target = model.body('target').id
    gid = model.geom('object').id
    qadr = int(model.jnt_qposadr[model.body_jntadr[target]])
    vadr = int(model.jnt_dofadr[model.body_jntadr[target]])
    roles = np.full(model.nbody, ROLE_ENV)
    roles[model.body('pad_left').id] = ROLE_THUMB
    roles[model.body('pad_right').id] = ROLE_OPPOSING
    recorder = ContactRecorder(model, target, roles, snapshot_step=round(8/fixture.timestep_s)) if record else None
    planes = np.flatnonzero(model.geom_type == int(mujoco.mjtGeom.mjGEOM_PLANE))
    planned = round(fixture.duration_s/fixture.timestep_s)
    raw, common, gaps, post = [], [], [], []
    full_states = []
    flag = mujoco.mjtState.mjSTATE_INTEGRATION
    full_state = np.empty(mujoco.mj_stateSize(model, flag)) if verify_full_state else None
    start = time.perf_counter()
    # Pads are initialized at their declared pregrasp; target is free throughout.
    command = .0031 if fixture.mechanism == 'necessary_floor' else fixture.jaw_command
    for name in ('left', 'right'):
        data.qpos[model.jnt_qposadr[model.joint(name).id]] = command
    data.ctrl[:] = command
    data.qvel[vadr+3] = fixture.initial_angular_speed
    if fixture.mechanism == 'applied_assistance':
        data.xfrc_applied[target, 2] = fixture.mass * 9.81
    for step in range(planned):
        if fixture.mechanism == 'intermittent_floor':
            mid = model.body_mocapid[model.body('env_support').id]
            if fixture.support_schedule == 'periodic':
                withdrawn = 2 <= data.time % 4 < 4
            elif fixture.support_schedule == 'single_burst':
                withdrawn = not (8 <= step*fixture.timestep_s < 8.1)
            else:
                raise ValueError('Unregistered support schedule')
            data.mocap_pos[mid, 2] = .5-fixture.half_z+.00015 - (.04 if withdrawn else 0)
        before_q, before_v = data.qpos[qadr:qadr+7].copy(), data.qvel[vadr:vadr+6].copy()
        if recorder:
            recorder.before_step(data, step)
        mujoco.mj_step(model, data)
        if recorder:
            recorder.after_step(data)
            center, rot = data.geom_xpos[gid], data.geom_xmat[gid].reshape(3, 3)
            plane_pos = data.geom_xpos[planes].copy()
            normals = data.geom_xmat[planes].reshape(-1, 3, 3)[:, :, 2].copy()
            projections = np.abs(normals @ rot) @ model.geom_size[gid]
            distance = np.sum(normals*(center-plane_pos), axis=1) - projections
            gaps.append(float(distance.min()))
            raw.append(np.r_[center, rot.ravel(), plane_pos.ravel(), normals.ravel()])
            hand = set()
            for contact in data.contact:
                b1, b2 = model.geom_bodyid[contact.geom1], model.geom_bodyid[contact.geom2]
                if target in (b1, b2) and contact.efc_address >= 0:
                    other = b1 if b2 == target else b2
                    if roles[other] > ROLE_ENV:
                        hand.add(int(roles[other]))
            angle = 2*np.arccos(np.clip(abs(before_q[3]), 0., 1.))
            common.append(bool(step*fixture.timestep_s >= 1 and
                               np.linalg.norm(before_q[:3]-[0, 0, .5]) < .04 and
                               np.linalg.norm(before_v[:3]) < .2 and angle < .8 and len(hand) == 2))
        post.append(data.qpos[qadr:qadr+7].copy())
        if verify_full_state:
            mujoco.mj_getState(model, data, full_state, flag)
            full_states.append(full_state.copy())
    if not record:
        return np.asarray(full_states) if verify_full_state else np.asarray(post)
    arrays = recorder.arrays()
    arrays.update(raw_geometry=np.asarray(raw), common_q=np.asarray(common), geometry_gap=np.asarray(gaps))
    if verify_full_state:
        arrays['integration_states'] = np.asarray(full_states)
    metadata = recorder.metadata()
    metadata.update(fixture=asdict(fixture), signature=fixture.signature, model_xml=xml,
                    target_body=target, target_geom=gid, target_qadr=qadr, target_vadr=vadr,
                    plane_geoms=planes.tolist(), target_half_size=model.geom_size[gid].tolist(),
                    length_scale_m=float(np.linalg.norm(model.geom_size[gid])), planned_steps=planned,
                    terminal_reason='controller_schedule_completed', global_common=True,
                    elapsed_s=time.perf_counter()-start,
                    task_contract='Free pregrasp retention; no acquisition claim; bilateral pad constraints, pose/speed bounds, and 15 contiguous seconds after 1s settling',
                    role='development_only')
    return arrays, metadata


def smoke(destination='calibration/development_controls_attempt_1'):
    rows = []
    for index, mechanism in enumerate(MECHANISMS):
        fixture = Fixture(mechanism=mechanism, seed=50000+index)
        arrays, metadata = run_fixture(fixture)
        plain = run_fixture(fixture, record=False)
        metadata['observer_bit_equal'] = bool(np.array_equal(plain, arrays['post_qpos']))
        if not metadata['observer_bit_equal']:
            raise RuntimeError('Observer changed physical trajectory')
        result = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata,
                          Calibration(), geometry_gap=arrays['geometry_gap'])
        b4 = evaluate(arrays['steps'], metadata['step_columns'], arrays['common_q'], metadata,
                      Calibration(), use_geometry=False)
        name = f'{index:02d}_{mechanism}'
        base = OUT / destination / name
        with output_path(base.with_suffix('.npz')).open('xb') as handle:
            np.savez_compressed(handle, **arrays)
        write_json(base.with_suffix('.json'), dict(metadata=metadata, result=result, b4=b4), exclusive=True)
        row = dict(mechanism=mechanism, verdict=result['no_external_load_verdict'],
                   no_contact=result['no_contact_result'], b4=b4['no_external_load_verdict'],
                   common_seconds=float(arrays['common_q'].sum()*fixture.timestep_s),
                   observer_bit_equal=metadata['observer_bit_equal'], elapsed_s=metadata['elapsed_s'],
                   max_load_ratio=result.get('max_environment_force_ratio'),
                   reason_codes=result['reason_codes'])
        print(row, flush=True)
        rows.append(row)
    write_json(OUT / destination / 'summary.json', rows, exclusive=True)
    return rows


if __name__ == '__main__':
    smoke()
