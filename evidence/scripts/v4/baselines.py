"""Explicit information-matched historical baselines; no counterfactual inputs."""
from __future__ import annotations

import numpy as np

from .contracts import Calibration, evaluate, longest_interval, validate


def historical(arrays, metadata, config=Calibration()):
    steps, q, columns = arrays['steps'], arrays['common_q'], metadata['step_columns']
    gap = arrays.get('geometry_gap')
    full = evaluate(steps, columns, q, metadata, config, geometry_gap=gap)
    result = {'B5': full}
    for name, options in (
            ('B4', dict(use_geometry=False)),
            ('A_no_geometry', dict(use_geometry=False)),
            ('A_no_torque', dict(use_torque=False)),
            ('A_binary_unknown_fail', dict(binary=True)),
            ('A_accumulated', dict(contiguous=False))):
        result[name] = evaluate(steps, columns, q, metadata, config, geometry_gap=gap, **options)
    net_columns = [f'env_net_{quantity}_{axis}' for quantity in ('force', 'torque') for axis in 'xyz']
    if all(k in columns for k in net_columns):
        net = steps.copy()
        for quantity, suffix in (('force', 'n'), ('torque', 'nm')):
            net[:, columns.index(f'env_abs_{quantity}_{suffix}')] = np.linalg.norm(
                steps[:, [columns.index(f'env_net_{quantity}_{axis}') for axis in 'xyz']], axis=1)
        result['A_net_aggregation'] = evaluate(net, columns, q, metadata, config, geometry_gap=gap)
    else:
        result['A_net_aggregation'] = dict(verdict='INDETERMINATE', trace_validity='INVALID')
    if full['trace_validity'] != 'VALID' or not full['applicable']:
        for name in ('B0', 'B1', 'B2', 'B3', 'B4_normal'):
            result[name] = dict(verdict='INDETERMINATE', trace_validity=full['trace_validity'])
        return result
    c, dt = validate(steps, columns, q, metadata, config)
    global_ok = metadata['global_common'] and not any(c[k].any() for k in (
        'applied_any', 'target_qpos_write', 'target_qvel_write'))
    common = np.asarray(q, dtype=bool) & global_ok
    paths_known = metadata.get('support_paths', {}).get('complete_for_declared_model', False)

    def timing(mask, accumulated=False):
        seconds = float(np.sum(mask)*dt) if accumulated else longest_interval(mask, dt)['duration_s']
        return dict(verdict='PASS' if seconds+config.duration_tolerance_s >= config.hold_s else 'FAIL',
                    duration_s=seconds, trace_validity='VALID')

    result['B0'] = timing(common, accumulated=True)
    result['B1'] = timing(common)
    result['B0']['scope'] = 'Accumulated common-Q proxy; native only if the adapter explicitly establishes equivalence'
    result['B1']['scope'] = 'Continuous common-Q; environmental load is intentionally not part of this contract'
    result['B2'] = dict(verdict=full['no_contact_result'], duration_s=full['no_contact_interval']['duration_s'],
                        trace_validity='VALID')
    if gap is None or np.asarray(gap).shape != common.shape or not np.isfinite(gap).all():
        result['B3'] = dict(verdict='INDETERMINATE', trace_validity='INVALID')
    else:
        result['B3'] = timing(common & (np.asarray(gap) > config.positive_gap_m))
        if result['B3']['verdict'] == 'PASS' and not paths_known:
            result['B3']['verdict'] = 'INDETERMINATE'
    if 'env_normal_n' in columns:
        normal_steps = steps.copy()
        normal_steps[:, columns.index('env_abs_force_n')] = steps[:, columns.index('env_normal_n')]
        result['B4_normal'] = evaluate(normal_steps, columns, q, metadata, config,
                                       use_geometry=False, use_torque=False)
    else:
        result['B4_normal'] = dict(verdict='INDETERMINATE', trace_validity='INVALID')
    return result


def verdict(record):
    return record.get('verdict', record.get('no_external_load_verdict', 'INDETERMINATE'))


def confusion(predictions, references):
    if len(predictions) != len(references):
        raise ValueError('Predictions and references must be paired')
    rows = {f'{a}_{b}': 0 for a in ('PASS', 'FAIL', 'INDETERMINATE')
            for b in ('PASS', 'FAIL', 'INDETERMINATE')}
    for prediction, reference in zip(predictions, references):
        rows[f'{reference}_{prediction}'] += 1
    positive = sum(rows[f'PASS_{b}'] for b in ('PASS', 'FAIL', 'INDETERMINATE'))
    negative = sum(rows[f'FAIL_{b}'] for b in ('PASS', 'FAIL', 'INDETERMINATE'))
    determinate = sum(rows[f'{a}_{b}'] for a in ('PASS', 'FAIL', 'INDETERMINATE') for b in ('PASS', 'FAIL'))
    return dict(n=len(predictions), reference_positive=positive, reference_negative=negative,
                false_accept=rows['FAIL_PASS'], false_reject=rows['PASS_FAIL'],
                unknown=sum(rows[f'{a}_INDETERMINATE'] for a in ('PASS', 'FAIL', 'INDETERMINATE')),
                coverage=determinate/len(predictions) if predictions else None,
                false_accept_rate=rows['FAIL_PASS']/negative if negative else None,
                false_reject_rate=rows['PASS_FAIL']/positive if positive else None,
                matrix_reference_prediction=rows)
