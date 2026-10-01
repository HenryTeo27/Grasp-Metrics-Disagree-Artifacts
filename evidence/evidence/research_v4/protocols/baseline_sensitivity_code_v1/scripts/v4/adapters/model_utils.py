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
