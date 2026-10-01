"""Publication-only figures from frozen artifacts, without simulator imports."""
from pathlib import Path
import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/research_v4'
FIG = ROOT/'paper_v4/figures'
RENDERS = FIG/'render_arrays'
COLORS = dict(B0='#777777', B1='#a6611a', B2='#3d719b', B3='#725a9e', B4='#15978d', B5='#c74458')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG/(name+'.pdf'), bbox_inches='tight', metadata={'CreationDate': None, 'ModDate': None})
    fig.savefig(FIG/(name+'.png'), dpi=190, bbox_inches='tight')
    plt.close(fig)


def static():
    plt.rcParams.update({'font.size': 10, 'font.family': 'DejaVu Sans', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.5))
    for ax, cid, title in zip(axes, ('final_control_000', 'final_control_001', 'final_control_002'),
                             ('Hand-only retention', 'Inactive contact records', 'Necessary floor support')):
        pixels = np.load(RENDERS/(cid+'.npy'), allow_pickle=False)
        record = read(OUT/'controls/final/cases'/(cid+'.json'))
        ax.imshow(pixels)
        ax.set_title(title, fontsize=11, pad=7)
        labels = f"No-contact: {record['methods']['B2']['verdict']}\nNo-load: {record['methods']['B5']['no_external_load_verdict']}\nRemoval: {record['counterfactual']['cell'].lower().replace('_', ' ')}"
        ax.text(.5, -.04, labels, transform=ax.transAxes, ha='center', va='top', fontsize=9, linespacing=1.5)
        ax.axis('off')
    fig.subplots_adjust(left=.01, right=.99, top=.94, bottom=.26, wspace=.07)
    save(fig, 'contract_examples')
    fig, ax = plt.subplots(figsize=(10.5, 3.65))
    ax.set(xlim=(0, 10.5), ylim=(0, 3.65))
    ax.axis('off')
    titles = ('Definition contrast', 'Physical intervention', 'Decision consequence')
    rows = (('One recorded trajectory', 'No-contact / no-load', 'Paired verdicts'),
            ('One full-state snapshot', 'Sham / environment removal', 'Four retention cells'),
            ('Same fixed K candidates', 'Seal first-PASS choice', 'New 15-second use'))
    for i, (title, row) in enumerate(zip(titles, rows)):
        y = 2.6-i*1.12
        ax.text(.10, y+.69, title, fontsize=10, weight='bold', color='#222222')
        for j, text in enumerate(row):
            x = .10+j*3.50
            ax.add_patch(Rectangle((x, y), 3.12, .53, facecolor='#f4f6f7', edgecolor='#89979d', linewidth=.8))
            ax.text(x+1.56, y+.265, text, ha='center', va='center', fontsize=9.5)
            if j < 2:
                ax.annotate('', (x+3.44, y+.265), (x+3.16, y+.265), arrowprops=dict(arrowstyle='->', color='#48585e', lw=1))
    save(fig, 'experimental_contrasts')


def quantitative():
    report = read(OUT/'analysis/formal_results.json')
    curves = read(OUT/'analysis/operating_curves.json')
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    ax = axes[0]
    for method in ('B0', 'B1', 'B2', 'B3', 'B4', 'B5'):
        rows = [r for r in curves['curves'] if r['method'] == method]
        x = [r['correct_accept_per_assigned'] for r in rows]
        y = [r['accepted_risk'] for r in rows]
        ax.plot(x, y, color=COLORS[method], marker='o' if method != 'B5' else 's',
                markersize=9 if method == 'B4' else 5, markerfacecolor='none' if method in ('B4', 'B5') else COLORS[method],
                lw=1.3, linestyle='--' if method == 'B5' else '-', label=method)
    ax.axhline(.05, ls=':', color='#9b9b9b', lw=.8)
    ax.set(xlim=(0, 1), ylim=(-.025, 1), xlabel='Correctly accepted / 240 controls', ylabel='False accepts / labeled accepts',
           title='Fixed-reference operating points')
    ax.legend(ncol=3, loc='upper right', fontsize=8, frameon=False)
    ax.grid(axis='y', color='#e2e6e8', linewidth=.5)
    ax = axes[1]
    for method in ('B0', 'B2', 'B4', 'B5'):
        rows = [r for r in report['utility']['summary'] if r['method'] == method]
        rows.sort(key=lambda r: r['k'])
        ax.plot([r['k'] for r in rows], [r['usable'] for r in rows], color=COLORS[method],
                marker='o' if method != 'B5' else 's', markersize=9 if method == 'B4' else 5,
                markerfacecolor='none' if method in ('B4', 'B5') else COLORS[method],
                lw=1.3, linestyle='--' if method == 'B5' else '-', label=method)
    ax.set(xticks=[1, 3, 6], xlim=(.7, 6.3), ylim=(0, 120), xlabel='Fixed candidate prefix K',
           ylabel='Usable selected candidates / 120 scenes', title='Independent added future retention')
    ax.legend(ncol=2, loc='upper left', fontsize=8, frameon=False)
    ax.grid(axis='y', color='#e2e6e8', linewidth=.5)
    fig.tight_layout(w_pad=2)
    save(fig, 'risk_coverage_utility')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--static-only', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        FIG = args.out.resolve()
    static()
    if not args.static_only:
        quantitative()
