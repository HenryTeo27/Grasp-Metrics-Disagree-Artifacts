"""Read-only pinned MuJoCo contact-solve recorder; no forward calls or state writes."""
from __future__ import annotations

import mujoco
import numpy as np

CONTACT_COLUMNS = ["step", "geom1", "geom2", "body1", "body2", "role", "efc_address", "dim", "dist"] + [
    f"point_{x}" for x in "xyz"] + [f"frame_{i}" for i in range(9)] + [
    f"local_{x}" for x in ("fn", "ft1", "ft2", "tn", "tt1", "tt2")] + [
    f"target_force_{x}" for x in "xyz"] + [f"target_com_torque_{x}" for x in "xyz"]
STEP_COLUMNS = ["step", "solve_time", "dt"] + [f"com_{x}" for x in "xyz"] + [
    f"quat_{x}" for x in "wxyz"] + [f"free_qvel_{i}" for i in range(6)] + [
    "env_count", "env_constraint_count", "env_force_threshold_count", "env_normal_n",
    "env_abs_force_n", "env_abs_torque_nm"] + [f"env_net_force_{x}" for x in "xyz"] + [
    f"env_net_torque_{x}" for x in "xyz"] + [
    "env_min_dist", "env_dist_present", "env_active_min_dist", "env_active_dist_present",
    "applied_any", "target_applied_norm", "target_qpos_write", "target_qvel_write",
    "geometry_clock_error", "contact_start", "contact_end"]
ROLE_ENV, ROLE_THUMB, ROLE_OPPOSING, ROLE_PALM = 0, 1, 2, 3


def body_scale(model, geom_id):
    size = model.geom_size[geom_id]
    kind = int(model.geom_type[geom_id])
    if kind == int(mujoco.mjtGeom.mjGEOM_BOX):
        half = size
    elif kind == int(mujoco.mjtGeom.mjGEOM_SPHERE):
        half = np.repeat(size[0], 3)
    elif kind == int(mujoco.mjtGeom.mjGEOM_CYLINDER):
        half = np.array([size[0], size[0], size[1]])
    elif kind == int(mujoco.mjtGeom.mjGEOM_CAPSULE):
        half = np.array([size[0], size[0], size[0] + size[1]])
    else:
        raise ValueError("Declare an object-frame bounding box for nonprimitive targets")
    return float(np.linalg.norm(half))


def support_paths(model, target):
    """Enumerate direct non-contact support paths, not a universal anti-cheat proof."""
    reasons = []
    joint_ids = list(range(int(model.body_jntadr[target]),
                           int(model.body_jntadr[target] + model.body_jntnum[target])))
    if len(joint_ids) != 1 or int(model.jnt_type[joint_ids[0]]) != int(mujoco.mjtJoint.mjJNT_FREE):
        reasons.append("TARGET_NOT_SINGLE_FREE_JOINT")
    if int(model.body_parentid[target]) != 0 or np.any(model.body_parentid == target):
        reasons.append("TARGET_NOT_SINGLE_WORLD_CHILD")
    if float(model.body_gravcomp[target]) != 0:
        reasons.append("TARGET_GRAVITY_COMPENSATION")
    for j in joint_ids:
        dof = int(model.jnt_dofadr[j])
        width = 6 if int(model.jnt_type[j]) == int(mujoco.mjtJoint.mjJNT_FREE) else 1
        if float(model.jnt_stiffness[j]) != 0 or np.any(model.dof_damping[dof:dof+width] != 0):
            reasons.append("TARGET_PASSIVE_JOINT_FORCE")
    for i in range(model.neq):
        typ = int(model.eq_type[i])
        objs = (int(model.eq_obj1id[i]), int(model.eq_obj2id[i]))
        if typ in (int(mujoco.mjtEq.mjEQ_CONNECT), int(mujoco.mjtEq.mjEQ_WELD)) and target in objs:
            reasons.append(f"TARGET_BODY_EQUALITY:{i}")
        elif typ == int(mujoco.mjtEq.mjEQ_JOINT) and any(j in objs for j in joint_ids):
            reasons.append(f"TARGET_JOINT_EQUALITY:{i}")
    target_sites = set(np.flatnonzero(model.site_bodyid == target).tolist())
    target_tendons = set()
    for t in range(model.ntendon):
        for w in range(int(model.tendon_adr[t]), int(model.tendon_adr[t] + model.tendon_num[t])):
            if int(model.wrap_type[w]) == int(mujoco.mjtWrap.mjWRAP_SITE) and int(model.wrap_objid[w]) in target_sites:
                target_tendons.add(t)
    if target_tendons:
        reasons.append("TARGET_TENDON_PATH")
    for i in range(model.nu):
        typ, obj = int(model.actuator_trntype[i]), int(model.actuator_trnid[i, 0])
        if ((typ in (int(mujoco.mjtTrn.mjTRN_JOINT), int(mujoco.mjtTrn.mjTRN_JOINTINPARENT)) and obj in joint_ids)
                or (typ == int(mujoco.mjtTrn.mjTRN_BODY) and obj == target)
                or (typ == int(mujoco.mjtTrn.mjTRN_SITE) and obj in target_sites)
                or (typ == int(mujoco.mjtTrn.mjTRN_TENDON) and obj in target_tendons)):
            reasons.append(f"TARGET_ACTUATOR:{i}")
    return dict(complete_for_declared_model=not reasons, reason_codes=reasons,
                scope="Single free primitive; direct equality/tendon/actuator/passive paths and applied arrays. "
                      "No claim to detect malicious plugins or opaque external callbacks.")


class ContactRecorder:
    def __init__(self, model, target_body, body_roles, snapshot_step=None):
        if mujoco.__version__ not in ("3.8.0", "3.3.2"):
            raise ValueError("Observer requires a pinned and separately qualified MuJoCo runtime")
        if int(model.opt.integrator) == int(mujoco.mjtIntegrator.mjINT_RK4):
            raise ValueError("RK4 has multiple solve stages; this observer does not cover it")
        self.model, self.target = model, int(target_body)
        self.roles = np.asarray(body_roles, dtype=int)
        if self.roles.shape != (model.nbody,):
            raise ValueError("One declared role per body required")
        self.joint = int(model.body_jntadr[self.target])
        if int(model.jnt_type[self.joint]) != int(mujoco.mjtJoint.mjJNT_FREE):
            raise ValueError("Recorder requires a free target")
        self.qadr = int(model.jnt_qposadr[self.joint])
        self.vadr = int(model.jnt_dofadr[self.joint])
        self.steps, self.contacts, self.controls, self.actuator_forces = [], [], [], []
        self.mocap, self.post_qpos, self.post_qvel = [], [], []
        self._force = np.zeros(6)
        self._previous = None
        self.before = None
        self.snapshot_step, self.snapshot = snapshot_step, None
        self.path_audit = support_paths(model, self.target)

    def before_step(self, data, step):
        q = data.qpos[self.qadr:self.qadr+7].copy()
        v = data.qvel[self.vadr:self.vadr+6].copy()
        writes = (False, False) if self._previous is None else (
            not np.array_equal(q, self._previous[0]), not np.array_equal(v, self._previous[1]))
        if self.snapshot_step == step:
            flag = mujoco.mjtState.mjSTATE_INTEGRATION
            state = np.empty(mujoco.mj_stateSize(self.model, flag))
            mujoco.mj_getState(self.model, data, state, flag)
            self.snapshot = dict(step=step, flag=int(flag), time=float(data.time), state=state)
        self.before = (step, float(data.time), q, v,
                       bool(np.any(data.xfrc_applied) or np.any(data.qfrc_applied)),
                       float(np.linalg.norm(data.xfrc_applied[self.target])) +
                       float(np.linalg.norm(data.qfrc_applied[self.vadr:self.vadr+6])), *writes)
        self.controls.append(data.ctrl.copy())
        self.mocap.append(np.r_[data.mocap_pos.ravel(), data.mocap_quat.ravel()])

    def after_step(self, data):
        m, b = self.model, self.target
        step, time, q, v, applied, target_applied, qw, vw = self.before
        com, quat = data.xipos[b].copy(), data.xquat[b].copy()
        rot = np.empty(9)
        mujoco.mju_quat2Mat(rot, q[3:])
        expected_com = q[:3] + rot.reshape(3, 3) @ m.body_ipos[b]
        clock_error = float(np.linalg.norm(com - expected_com))
        net_f, net_t = np.zeros(3), np.zeros(3)
        count = active = nonzero = 0
        normal = abs_f = abs_t = 0.
        closest, active_dist = 1e10, 1e10
        start = len(self.contacts)
        for i in range(data.ncon):
            c = data.contact[i]
            b1, b2 = int(m.geom_bodyid[c.geom1]), int(m.geom_bodyid[c.geom2])
            if b not in (b1, b2):
                continue
            other = b2 if b1 == b else b1
            role = int(self.roles[other])
            mujoco.mj_contactForce(m, data, i, self._force)
            local = self._force.copy()
            frame = np.asarray(c.frame).reshape(3, 3)
            sign = 1. if b2 == b else -1.
            force = sign * (frame.T @ local[:3])
            torque = np.cross(np.asarray(c.pos)-com, force) + sign * (frame.T @ local[3:])
            self.contacts.append([step, c.geom1, c.geom2, b1, b2, role, c.efc_address, c.dim, c.dist,
                                  *c.pos, *c.frame, *local, *force, *torque])
            if role == ROLE_ENV:
                count += 1
                active += int(c.efc_address >= 0)
                nonzero += int(local[0] > 1e-4)
                normal += local[0]
                abs_f += np.linalg.norm(force)
                abs_t += np.linalg.norm(torque)
                net_f += force
                net_t += torque
                closest = min(closest, c.dist)
                if c.efc_address >= 0:
                    active_dist = min(active_dist, c.dist)
        self.steps.append([step, time, m.opt.timestep, *com, *quat, *v,
                           count, active, nonzero, normal, abs_f, abs_t, *net_f, *net_t,
                           closest, bool(count), active_dist, bool(active), applied, target_applied,
                           qw, vw, clock_error, start, len(self.contacts)])
        self.actuator_forces.append(data.actuator_force.copy())
        post_q = data.qpos[self.qadr:self.qadr+7].copy()
        post_v = data.qvel[self.vadr:self.vadr+6].copy()
        self.post_qpos.append(post_q)
        self.post_qvel.append(post_v)
        self._previous = (post_q, post_v)

    def arrays(self):
        n = len(self.steps)
        arrays = dict(steps=np.asarray(self.steps, dtype=float).reshape(n, len(STEP_COLUMNS)),
                      contacts=np.asarray(self.contacts, dtype=float).reshape(-1, len(CONTACT_COLUMNS)),
                      controls=np.asarray(self.controls, dtype=float).reshape(n, self.model.nu),
                      actuator_forces=np.asarray(self.actuator_forces, dtype=float).reshape(n, self.model.nu),
                      mocap=np.asarray(self.mocap, dtype=float).reshape(n, 7*self.model.nmocap),
                      post_qpos=np.asarray(self.post_qpos), post_qvel=np.asarray(self.post_qvel))
        if self.snapshot is not None:
            arrays["snapshot_state"] = self.snapshot["state"]
        return arrays

    def metadata(self):
        snap = None if self.snapshot is None else {k: v for k, v in self.snapshot.items() if k != "state"}
        return dict(observer_version="merged-v4-contact-solve-2", mujoco_version=mujoco.__version__,
                    target_body=self.target, target_qadr=self.qadr, target_vadr=self.vadr,
                    step_columns=STEP_COLUMNS,
                    contact_columns=CONTACT_COLUMNS, body_roles=self.roles.tolist(),
                    mass_kg=float(self.model.body_mass[self.target]),
                    gravity=self.model.opt.gravity.tolist(), support_paths=self.path_audit,
                    snapshot=snap, sample_convention="pre-integration solve state with separately named post states",
                    force_convention="contact-frame force/torque acts on geom2; world wrench about target COM",
                    geometry_clock_max_error=max((r[STEP_COLUMNS.index("geometry_clock_error")] for r in self.steps), default=0.))
