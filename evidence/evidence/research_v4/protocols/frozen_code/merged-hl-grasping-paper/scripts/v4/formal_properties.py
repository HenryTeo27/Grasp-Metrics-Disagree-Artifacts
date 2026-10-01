"""Registered representation tests; paired re-executions are not new scene N."""
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from . import controls
from .baselines import historical, verdict
from .common import OUT, output_path, read_json, sha256, write_json
from .contracts import Calibration


def run():
    from .protocol import verify_lock
    lock = verify_lock()
    config = Calibration(**lock['calibration'])
    rows = [r for r in read_json(OUT/'protocols/final_controls.json') if r['representation_selected']]
    results = []
    for row in rows:
        source = OUT/'controls/final/cases'/row['case_id']
        original = read_json(source.with_suffix('.json'))
        if sha256(source.with_suffix('.npz')) != original['trace_sha256']:
            raise RuntimeError('Original control trace changed')
        with np.load(source.with_suffix('.npz'), allow_pickle=False) as z:
            integration = z['integration_states']
        original_build = controls.build

        def no_inactive_margin(fixture):
            _, xml = original_build(fixture)
            root = ET.fromstring(xml)
            geom = root.find(".//geom[@name='support']")
            geom.set('margin', '0')
            geom.set('gap', '0')
            xml = ET.tostring(root, encoding='unicode')
            return mujoco.MjModel.from_xml_string(xml), xml

        controls.build = no_inactive_margin
        try:
            arrays, metadata = controls.run_fixture(controls.Fixture(**row['parameters']), verify_full_state=True)
        finally:
            controls.build = original_build
        equal = np.array_equal(integration, arrays['integration_states'])
        methods = historical(arrays, metadata, config)
        target = OUT/'controls/properties'/row['case_id']
        with output_path(target.with_suffix('.npz')).open('xb') as handle:
            np.savez_compressed(handle, **arrays)
        result = dict(case_id=row['case_id'], full_state_bit_equal=equal,
                      original={k: verdict(v) for k, v in original['methods'].items()},
                      transformed={k: verdict(v) for k, v in methods.items()},
                      property_interpretable=equal, extra_physics_steps=metadata['planned_steps'],
                      metadata=metadata, trace_sha256=sha256(target.with_suffix('.npz')),
                      transformation='Only environmental support margin and gap changed from .020/.020 to 0/0; '
                                     'inactive-contact representation hypothesis accepted only when whole integration trace is bit-identical')
        write_json(target.with_suffix('.json'), result, exclusive=True)
        results.append({k: v for k, v in result.items() if k not in ('metadata',)})
    write_json(OUT/'controls/properties/summary.json', dict(paired_cases=len(results), independent_new_scenes=0, rows=results), exclusive=True)
    return results


if __name__ == '__main__':
    print(run())
