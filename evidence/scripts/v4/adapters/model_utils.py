"""Qualified model cloning and declared object-frame geometry bounds."""
import mujoco
import numpy as np


def model_factory(model):
    buffer = np.empty(mujoco.mj_sizeModel(model), dtype=np.uint8)
    mujoco.mj_saveModel(model, buffer=buffer)
    binary = buffer.tobytes()
    return lambda: mujoco.MjModel.from_binary_path('snapshot.mjb', {'snapshot.mjb': binary})


def geom_box(model, gid):
    kind, size = model.geom_type[gid], model.geom_size[gid]
    offset = np.zeros(3)
    if kind == mujoco.mjtGeom.mjGEOM_BOX:
        half = size.copy()
    elif kind == mujoco.mjtGeom.mjGEOM_SPHERE:
        half = np.repeat(size[0], 3)
    elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
        half = np.array([size[0], size[0], size[1]])
    elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
        half = np.array([size[0], size[0], size[0]+size[1]])
    elif kind == mujoco.mjtGeom.mjGEOM_ELLIPSOID:
        half = size.copy()
    elif kind == mujoco.mjtGeom.mjGEOM_MESH:
        mid = int(model.geom_dataid[gid])
        first, count = int(model.mesh_vertadr[mid]), int(model.mesh_vertnum[mid])
        vertices = model.mesh_vert[first:first+count].astype(float)
        low, high = vertices.min(axis=0), vertices.max(axis=0)
        offset, half = (high+low)/2, (high-low)/2
    else:
        raise ValueError(f'Unsupported finite geometry {kind}')
    return offset, half


def object_bounds(model, target):
    vertices = []
    signs = np.array([[a, b, c] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)])
    for gid in np.flatnonzero(model.geom_bodyid == target):
        if not (model.geom_contype[gid] or model.geom_conaffinity[gid]):
            continue
        offset, half = geom_box(model, gid)
        rotation = np.empty(9)
        mujoco.mju_quat2Mat(rotation, model.geom_quat[gid])
        vertices.extend((offset+signs*half) @ rotation.reshape(3, 3).T + model.geom_pos[gid])
    if not vertices:
        raise ValueError('Target has no collision geometry')
    vertices = np.asarray(vertices)
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    return dict(body_frame_min=low.tolist(), body_frame_max=high.tolist(),
                length_scale_m=float(np.linalg.norm((high-low)/2)),
                convention='Half diagonal of declared body-frame union bounding box; conservative geom boxes, fixed across poses')


class BoxEnvironmentGeometry:
    """Conservative separating-axis clearance of a target box from all permitted environment geoms."""
    def __init__(self, model, target_geom, roles):
        if model.geom_type[target_geom] != mujoco.mjtGeom.mjGEOM_BOX or model.npair:
            raise ValueError('Adapter requires one box and no explicit collision pairs')
        self.target = target_geom
        self.half = model.geom_size[target_geom].copy()
        self.boxes, self.planes, offsets, half = [], [], [], []
        for gid in range(model.ngeom):
            if gid == target_geom or roles[model.geom_bodyid[gid]] != 0:
                continue
            if not (model.geom_contype[target_geom] & model.geom_conaffinity[gid] or
                    model.geom_contype[gid] & model.geom_conaffinity[target_geom]):
                continue
            if model.geom_type[gid] == mujoco.mjtGeom.mjGEOM_PLANE:
                self.planes.append(gid)
            else:
                offset, bounds = geom_box(model, gid)
                self.boxes.append(gid)
                offsets.append(offset)
                half.append(bounds)
        self.offsets, self.halves = np.asarray(offsets).reshape(-1, 3), np.asarray(half).reshape(-1, 3)

    def sample(self, data):
        rt = data.geom_xmat[self.target].reshape(3, 3)
        ct = data.geom_xpos[self.target]
        rb = data.geom_xmat[self.boxes].reshape(-1, 3, 3)
        cb = data.geom_xpos[self.boxes]+np.einsum('nij,nj->ni', rb, self.offsets)
        gaps = []
        if len(self.boxes):
            target_axes = np.broadcast_to(rt.T, (len(rb), 3, 3))
            other_axes = rb.transpose(0, 2, 1)
            cross = np.cross(target_axes[:, :, None, :], other_axes[:, None, :, :]).reshape(-1, 9, 3)
            axes = np.concatenate([target_axes, other_axes, cross], axis=1)
            norms = np.linalg.norm(axes, axis=2)
            axes /= np.where(norms < 1e-10, 1., norms)[:, :, None]
            distance = np.abs(np.einsum('nka,na->nk', axes, cb-ct))
            radius_t = np.abs(np.einsum('nka,aj->nkj', axes, rt)) @ self.half
            radius_b = np.sum(np.abs(np.einsum('nka,naj->nkj', axes, rb))*self.halves[:, None, :], axis=2)
            separates = distance-radius_t-radius_b
            separates[norms < 1e-10] = -np.inf
            gaps.extend(separates.max(axis=1))
        rp = data.geom_xmat[self.planes].reshape(-1, 3, 3)
        cp = data.geom_xpos[self.planes]
        normals = rp[:, :, 2]
        gaps.extend(np.sum(normals*(ct-cp), axis=1) - np.abs(normals@rt) @ self.half)
        raw = np.r_[ct, rt.ravel(), cb.ravel(), rb.ravel(), cp.ravel(), normals.ravel()]
        return float(min(gaps, default=1e10)), raw

    def specification(self):
        return dict(target_half_size=self.half.tolist(), environment_box_geoms=self.boxes,
                    environment_box_halves=self.halves.tolist(), environment_plane_geoms=self.planes,
                    raw_layout='target_center(3), target_rotation(9), box_centers(3N), box_rotations(9N), '
                               'plane_origins(3P), plane_normals(3P)',
                    semantics='Positive SAT gap certifies separation of enclosing boxes; overlap can be conservative '
                              'for non-box shapes and yields uncertainty rather than asserted mesh penetration.')
