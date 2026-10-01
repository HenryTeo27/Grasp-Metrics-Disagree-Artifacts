"""V4.5 publication composition only. No scientific-module or simulator imports."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper_v45'
BUILD = ROOT / 'build_v45'
DATA = ROOT / 'evidence/research_v4'
DIST = ROOT / 'dist'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def protected_paths():
    paths = {ROOT / 'README.md'}
    for name in ('paper', 'paper_v4', 'scripts/v4', 'tests/v4', 'reproduce_v4'):
        paths.update(p for p in (ROOT / name).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    paths.update(p for p in DATA.rglob('*')
                 if p.is_file() and p.suffix in ('.json', '.csv', '.md', '.py'))
    paths.update(p for p in DIST.glob('*v3*') if p.is_file())
    paths.update(p for p in DIST.glob('*v4_*') if p.is_file() and 'v4_5' not in p.name)
    paths.add(DIST / 'merged_hl_grasping_paper_v4.pdf')
    return sorted(paths)


def prepare():
    BUILD.mkdir(parents=True, exist_ok=True)
    snapshot = BUILD / 'protected_before.json'
    if not snapshot.exists():
        write(snapshot, {p.relative_to(ROOT).as_posix(): sha(p) for p in protected_paths()})
    for name in ('numbers', 'results', 'control_table', 'external_table', 'utility_table',
                 'mechanism_table', 'reference_details', 'history', 'candidate_table', 'distributions'):
        copy(ROOT / 'paper_v4/generated' / (name + '.tex'), PAPER / 'generated' / (name + '.tex'))
    for name in ('02_contracts.tex', '03_design.tex', '04_results.tex'):
        copy(ROOT / 'paper_v4/sections' / name, PAPER / 'detail' / name)
    copy(ROOT / 'paper_v4/references.bib', PAPER / 'references.bib')
    for name in ('experimental_contrasts.pdf', 'risk_coverage_utility.pdf'):
        copy(ROOT / 'paper_v4/figures' / name, PAPER / 'figures' / name)
    for name in ('v3_physics_and_budget.pdf', 'v3_family_replication.pdf'):
        copy(ROOT / 'paper/figures' / name, PAPER / 'figures' / name)
    for name in ('v3_physics.tex', 'v3_families.tex', 'v3_budget.tex', 'v3_blocks.tex'):
        copy(ROOT / 'paper/tables' / name, PAPER / 'historical' / name)
    return {'status': 'PREPARED', 'protected_files': len(read(snapshot))}


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42})
    output = PAPER / 'figures'
    output.mkdir(parents=True, exist_ok=True)

    def save(fig, name):
        fig.savefig(output / (name + '.pdf'), bbox_inches='tight', pad_inches=.02,
                    metadata={'CreationDate': None, 'ModDate': None})
        fig.savefig(output / (name + '.png'), dpi=230, bbox_inches='tight', pad_inches=.02)
        plt.close(fig)

    records = [read(DATA / f'controls/final/cases/final_control_{i:03d}.json') for i in range(4)]
    cells = [r['counterfactual']['cell'] for r in records]
    assert cells == ['BOTH_RETAIN', 'BOTH_RETAIN', 'DEPENDENT', 'BOTH_RETAIN'], cells
    fig = plt.figure(figsize=(7.0, 3.4))
    grid = fig.add_gridspec(2, 3, height_ratios=[1, 1.05], hspace=.06, wspace=.04)
    for i, title in enumerate(('(a) Hand-only', '(b) Inactive records', '(c) Necessary floor')):
        ax = fig.add_subplot(grid[0, i])
        pixels = np.load(ROOT / f'paper_v4/figures/render_arrays/final_control_{i:03d}.npy', allow_pickle=False)
        ax.imshow(pixels)
        ax.set_title(title, fontsize=10, pad=2)
        ax.axis('off')
    ax = fig.add_subplot(grid[1, :])
    ax.axis('off')
    rows = []
    for name, record in zip(('(a) Hand-only', '(b) Inactive records', '(c) Necessary floor', '(d) Redundant floor*'), records):
        rows.append([name, record['methods']['B2']['verdict'].lower(),
                     record['methods']['B5']['no_external_load_verdict'].lower(),
                     record['counterfactual']['cell'].lower().replace('_', ' ')])
    table = ax.table(cellText=rows, colLabels=['Recorded case', 'No-contact', 'No-load', '3 s branches'],
                     colWidths=[.32, .20, .20, .28], cellLoc='center', loc='upper center')
    table.auto_set_font_size(False)
    table.set_fontsize(9.4)
    table.scale(1, 1.18)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor('white')
        cell.set_facecolor('#e9edf0' if r == 0 else ('#f2f6f6' if r == 4 else 'white'))
        if r == 0:
            cell.set_text_props(weight='bold')
    ax.text(0, -.01, '*Redundant-floor result; not pictured.', fontsize=8.5)
    fig.subplots_adjust(left=.01, right=.99, top=.94, bottom=.05)
    save(fig, 'targets')

    fig, ax = plt.subplots(figsize=(3.5, 1.52))
    ax.axis('off')
    contrasts = [
        ['Definition', 'Recorded\ntrajectory', 'Contact /\nload rule', 'Paired\nverdicts'],
        ['Intervention', 'Full state +\ninput tape', 'Sham /\nremoval', '3 s retention\ncells'],
        ['Selection', 'Same K\ncandidates', 'First-pass\nchoice', 'Sealed\n15 s use'],
    ]
    table = ax.table(cellText=contrasts, colLabels=['Comparison', 'Held fixed', 'Changed', 'Measured'],
                     colWidths=[.23, .27, .23, .27], cellLoc='left', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.85)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor('white')
        cell.set_facecolor('#e9edf0' if r == 0 else ('#f3f7f7' if r % 2 else 'white'))
        if r == 0 or c == 0:
            cell.set_text_props(weight='bold')
    fig.subplots_adjust(left=.01, right=.99, top=.99, bottom=.01)
    save(fig, 'contrasts')

    with (DATA / 'analysis/u2_choices_and_outcomes.csv').open(encoding='utf-8-sig', newline='') as stream:
        all_rows = list(csv.DictReader(stream))
    methods = ('B0', 'B1', 'B2', 'B3', 'B4_normal', 'B4', 'B5')
    counts = {}
    selected = {}
    for method in methods:
        rows = [r for r in all_rows if int(r['k']) == 6 and r['method'] == method]
        assert len(rows) == 120, (method, len(rows))
        n = {'usable': 0, 'failed': 0, 'abstained': 0}
        selected[method] = {}
        for row in rows:
            abstained = row['abstained'].lower() in ('true', '1')
            selected[method][row['case_id']] = None if abstained else row['selected_job']
            if abstained:
                n['abstained'] += 1
            else:
                assert row['future_status'] == 'VALID', row
                usable = row['usable'].lower() in ('true', '1')
                n['usable' if usable else 'failed'] += 1
        assert sum(n.values()) == 120
        counts[method] = n
    assert counts['B0'] == dict(usable=15, failed=25, abstained=80)
    assert counts['B1'] == dict(usable=15, failed=21, abstained=84)
    for method in methods[2:]:
        assert counts[method] == dict(usable=10, failed=3, abstained=107)
    assert selected['B2'] == selected['B4'] == selected['B5']
    plotted = ('B0', 'B1', 'B2', 'B4', 'B5')
    names = ('Native (B0)', 'Continuous (B1)', 'No-contact (B2)', 'Full-wrench (B4)', 'Integrated (B5)')
    fig, ax = plt.subplots(figsize=(3.5, 2.12))
    left = np.zeros(len(plotted))
    for category, label, color in zip(('usable', 'failed', 'abstained'),
                                     ('Usable', 'Failed', 'Abstained'),
                                     ('#137c78', '#bb4b55', '#dce1e5')):
        values = np.array([counts[m][category] for m in plotted])
        ax.barh(names, values, left=left, label=label, color=color, height=.61)
        for i, (start, value) in enumerate(zip(left, values)):
            ax.text(start + value/2, i, str(value), ha='center', va='center',
                    fontsize=7, color='#202b30' if category == 'abstained' else 'white')
        left += values
    ax.invert_yaxis()
    ax.set(xlim=(0, 120), xlabel='Assigned scenes (K = 6)', xticks=(0, 20, 40, 60, 80, 100, 120))
    ax.tick_params(axis='y', length=0, labelsize=7)
    ax.tick_params(axis='x', labelsize=7)
    ax.xaxis.label.set_size(7)
    ax.legend(ncol=3, loc='lower left', bbox_to_anchor=(-.05, 1.0), frameon=False, fontsize=7,
              columnspacing=1, handlelength=1.2)
    fig.tight_layout(pad=.3)
    save(fig, 'selection')
    provenance = {'scope': 'Editorial recomposition; no new physical measurements',
                  'k6_stacks': counts, 'B2_B4_B5_all_choices_identical': True,
                  'control_examples': [f'final_control_{i:03d}' for i in range(4)],
                  'input_hashes': {p.relative_to(ROOT).as_posix(): sha(p) for p in
                                  [DATA / 'analysis/u2_choices_and_outcomes.csv'] +
                                  [DATA / f'controls/final/cases/final_control_{i:03d}.json' for i in range(4)]}}
    write(BUILD / 'figure_checks.json', provenance)
    return provenance


def compile_papers(source=PAPER, jobs=None):
    tex = shutil.which('pdflatex') or r'C:/Program Files/MiKTeX/miktex/bin/x64/pdflatex.exe'
    bib = shutil.which('bibtex') or r'C:/Program Files/MiKTeX/miktex/bin/x64/bibtex.exe'
    results = {}
    for stem in jobs or ('main', 'main_review', 'supplement', 'supplement_review'):
        commands = ([tex, '-interaction=nonstopmode', '-halt-on-error', stem + '.tex'],
                    [bib, stem],
                    [tex, '-interaction=nonstopmode', '-halt-on-error', stem + '.tex'],
                    [tex, '-interaction=nonstopmode', '-halt-on-error', stem + '.tex'])
        for index, command in enumerate(commands):
            result = subprocess.run(command, cwd=source, capture_output=True, text=True, errors='replace')
            (source / (stem + f'.pass{index}.txt')).write_text(result.stdout + result.stderr, encoding='utf-8')
            if result.returncode:
                raise RuntimeError(result.stdout[-4000:] + result.stderr[-2000:])
        log = (source / (stem + '.log')).read_text(encoding='utf-8', errors='replace')
        warnings = [line for line in log.splitlines()
                    if any(x in line for x in ('Overfull', 'undefined', 'multiply defined', 'LaTeX Warning'))]
        if any('undefined' in w or 'multiply defined' in w for w in warnings):
            raise RuntimeError(f'{stem}: {warnings}')
        results[stem] = {'pdf_bytes': (source / (stem + '.pdf')).stat().st_size,
                         'warnings': warnings}
        print(json.dumps({stem: results[stem]}), flush=True)
    return results


def verify_protected():
    expected = read(BUILD / 'protected_before.json')
    errors = [name for name, digest in expected.items() if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    if errors:
        raise RuntimeError({'protected_files_changed': errors})
    return {'status': 'UNCHANGED', 'files': len(expected)}


def zip_tree(folder, target, accept=lambda p: True):
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and accept(path):
                z.write(path, path.relative_to(folder))


def core_raw():
    inventory = read(ROOT / 'build_v4/evidence_final/raw_trace_manifest.json')['files']
    entries = [r for r in inventory if r['path'].startswith('evidence/research_v4/controls/')]
    assert len(entries) == 248, len(entries)
    target = DIST / 'merged_hl_grasping_paper_v4_5_core_raw.zip'
    if target.exists():
        raise FileExistsError(target)
    total = 0
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for index, row in enumerate(entries):
            source = ROOT / row['path']
            assert source.stat().st_size == row['bytes'] and sha(source) == row['sha256'], row['path']
            z.write(source, row['path'])
            total += row['bytes']
            if (index + 1) % 40 == 0:
                print(f'Core raw: {index + 1}/248', flush=True)
        z.writestr('CORE_RAW_MANIFEST.json', json.dumps({'scope': '240 final controls + 8 representation partners',
                    'files': entries, 'bytes': total, 'independent_raw_rescoring_scope': 'Three examples in label package'}, indent=2))
        z.writestr('README.txt', 'V4.5 controlled raw evidence companion.\n248 original primitive-control NPZ traces.\n'
                   'No new simulations or new reference adjudication. No third-party robot meshes.\n'
                   'Extract alongside the label package to expose these relative paths.\n'
                   'The original offline verifier still rescores only its three declared examples.\n'
                   'Full natural-task raw access is not supplied by this archive.\n')
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
    result = {'path': str(target), 'files': len(entries), 'raw_bytes': total, 'sha256': sha(target)}
    write(BUILD / 'core_raw_check.json', result)
    return result


def release():
    names = {'main': '', 'main_review': '_review_preparation',
             'supplement': '_supplement', 'supplement_review': '_supplement_review_preparation'}
    for stem, suffix in names.items():
        copy(PAPER / (stem + '.pdf'), DIST / ('merged_hl_grasping_paper_v4_5' + suffix + '.pdf'))
    source_zip = DIST / 'merged_hl_grasping_paper_v4_5_latex_source.zip'
    zip_tree(PAPER, source_zip, lambda p: p.suffix in ('.tex', '.bib', '.bbl', '.md') or
             (p.parent.name == 'figures' and p.suffix == '.pdf'))
    package = BUILD / 'evidence_package'
    if package.exists():
        if not (package / 'README_V45.md').is_file() or not (package / 'scripts/v45_editorial.py').is_file():
            raise FileExistsError('Existing directory is not this editorial package: ' + str(package))
    else:
        shutil.copytree(ROOT / 'build_v4/evidence_final', package)
    copy(ROOT / 'scripts/v45_editorial.py', package / 'scripts/v45_editorial.py')
    copy(ROOT / 'README_V45.md', package / 'README_V45.md')
    copy(ROOT / 'README_V45.md', package / 'README.md')
    copy(BUILD / 'figure_checks.json', package / 'notes/v45/figure_checks.json')
    copy(BUILD / 'core_raw_check.json', package / 'notes/v45/core_raw_check.json')
    for path in PAPER.rglob('*'):
        if path.is_file() and (path.suffix in ('.tex', '.bib', '.bbl', '.md') or
                              (path.parent.name == 'figures' and path.suffix == '.pdf')):
            copy(path, package / 'paper_v45' / path.relative_to(PAPER))
    lines = [sha(p) + '  ' + p.relative_to(package).as_posix() for p in sorted(package.rglob('*'))
             if p.is_file() and p.name != 'MANIFEST.sha256']
    (package / 'MANIFEST.sha256').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    zip_tree(package, DIST / 'merged_hl_grasping_paper_v4_5_evidence.zip')
    return {'status': 'PACKAGED_REQUIRES_INDEPENDENT_CHECK', 'source': str(source_zip),
             'evidence_directory': str(package), 'evidence_files': len(lines)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'figures', 'compile', 'protected', 'core-raw', 'release'])
    parser.add_argument('--source', type=Path, default=PAPER)
    parser.add_argument('--jobs', nargs='+')
    args = parser.parse_args()
    actions = {'prepare': prepare, 'figures': figures, 'protected': verify_protected,
               'core-raw': core_raw, 'release': release,
               'compile': lambda: compile_papers(args.source.resolve(), args.jobs)}
    print(json.dumps(actions[args.action](), indent=2))


if __name__ == '__main__':
    main()
