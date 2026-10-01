"""Retrieve only the pinned Shadow mesh dependencies needed by the public example."""
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

from .common import OUT, sha256, write_json

COMMIT = '9da3f77e7ef4cb588cefb3bae7209d20522062d8'
SOURCE_COMMIT = 'd9ea6cf282de1f463c20fa54b4f68d7025bad40e'


def prepare():
    root = OUT / 'external/dexgraspbench/dependency_source'
    target = root / 'third_party/mujoco_menagerie/shadow_hand'
    xml = ET.parse(root / 'assets/hand/shadow/right_hand.xml')
    names = sorted({p.attrib['file'] for p in xml.findall('.//mesh') if 'file' in p.attrib})
    files = ['LICENSE'] + ['assets/' + name for name in names]
    records = []
    for relative in files:
        dest = (target / relative).resolve()
        if not dest.is_relative_to(target.resolve()):
            raise ValueError('Asset path escapes dependency directory')
        url = f'https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{COMMIT}/shadow_hand/{relative}'
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with urllib.request.urlopen(url, timeout=90) as response:
                payload = response.read()
            with dest.open('xb') as handle:
                handle.write(payload)
        records.append(dict(path=str(dest.relative_to(root)), source=url, sha256=sha256(dest), bytes=dest.stat().st_size))
        print(relative, dest.stat().st_size, flush=True)
    write_json(OUT / 'external/dexgraspbench/dependency_manifest.json',
               dict(source_commit=SOURCE_COMMIT, menagerie_commit=COMMIT, files=records,
                    method='Pinned raw asset retrieval after HTTPS submodule clone failed; not a complete submodule checkout',
                    redistribution='Excluded pending per-component license review'))


if __name__ == '__main__':
    prepare()
