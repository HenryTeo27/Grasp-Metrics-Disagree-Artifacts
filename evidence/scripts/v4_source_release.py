"""Build the standalone source ZIP in isolation and compare PDF text/pages."""
from pathlib import Path
import json
import shutil
import subprocess
import zipfile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'paper_v4'
DIST = ROOT/'dist'
TEX = Path('C:/Program Files/MiKTeX/miktex/bin/x64')


def run():
    stem = 'merged_hl_grasping_paper_v4'
    source_zip = DIST/(stem+'_latex_source.zip')
    target_pdf = DIST/(stem+'.pdf')
    build = ROOT/'build_v4/source_zip_check_1'
    if source_zip.exists() or target_pdf.exists() or build.exists():
        raise FileExistsError('Refuse to replace an existing V4 source release')
    paths = set(SOURCE.glob('*.tex')) | set(SOURCE.glob('*.bib')) | {SOURCE/'main.bbl', SOURCE/'BUILD.md'}
    paths.update((SOURCE/'sections').glob('*.tex'))
    paths.update((SOURCE/'generated').glob('*.tex'))
    paths.update((SOURCE/'figures').glob('*.pdf'))
    with zipfile.ZipFile(source_zip, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(paths):
            archive.write(path, path.relative_to(SOURCE))
    build.mkdir(parents=True)
    with zipfile.ZipFile(source_zip) as archive:
        archive.extractall(build)
    commands = [('pdflatex.exe', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'),
                ('bibtex.exe', 'main'), ('pdflatex.exe', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'),
                ('pdflatex.exe', '-interaction=nonstopmode', '-halt-on-error', 'main.tex')]
    for i, command in enumerate(commands):
        result = subprocess.run([str(TEX/command[0]), *command[1:]], cwd=build, capture_output=True)
        (build/f'command_{i}.txt').write_bytes(result.stdout+b'\n'+result.stderr)
        if result.returncode:
            raise RuntimeError(result.stdout[-3000:].decode(errors='replace'))
    left, right = PdfReader(SOURCE/'main.pdf'), PdfReader(build/'main.pdf')
    texts_left, texts_right = [p.extract_text() for p in left.pages], [p.extract_text() for p in right.pages]
    assert texts_left == texts_right, 'Independent source build differs in text or page count'
    log = (build/'main.log').read_text(encoding='utf-8', errors='replace')
    bad = [term for term in ('undefined references', 'undefined citations', 'Overfull', '! LaTeX Error') if term in log]
    assert not bad, bad
    shutil.copy2(SOURCE/'main.pdf', target_pdf)
    result = dict(status='PASS', pages=len(left.pages), pdf_text_equal=True, source_zip_files=len(paths),
        isolated_directory=str(build), build='pdflatex / bibtex / pdflatex / pdflatex',
        unresolved_references_or_overfull=bad, preserved_bbl=True,
        source_zip=str(source_zip), pdf=str(target_pdf))
    (ROOT/'build_v4/source_verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
