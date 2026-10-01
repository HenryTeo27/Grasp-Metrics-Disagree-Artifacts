"""Render and extract the complete V4 manuscript for human-readable QA."""
from pathlib import Path
import argparse
import json
import subprocess

from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def inspect(pdf, destination):
    destination.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(pdf)
    pages = [page.extract_text() for page in reader.pages]
    text = '\n\n'.join(pages)
    bad = {repr(c): text.count(c) for c in ('\ufffd', '\ufffe', '\x00', '-\u00bf') if c in text}
    if bad:
        raise RuntimeError('PDF encoding errors: '+str(bad))
    (destination/'extracted.txt').write_text(text, encoding='utf-8')
    subprocess.run(['pdftoppm', '-png', '-scale-to', '1500', str(pdf), str(destination/'page')], check=True, capture_output=True)
    images = sorted(destination.glob('page-*.png'))
    assert len(images) == len(pages)
    thumb_w, thumb_h, gutter = 330, 485, 12
    sheet = Image.new('RGB', (4*thumb_w+5*gutter, 3*thumb_h+4*gutter), '#d6d9dd')
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(images):
        frame = Image.open(path).convert('RGB')
        frame.thumbnail((thumb_w, thumb_h-20))
        x, y = gutter+(i % 4)*(thumb_w+gutter), gutter+(i//4)*(thumb_h+gutter)
        sheet.paste(frame, (x, y+20))
        draw.text((x, y), f'Page {i+1}', fill='black')
    sheet.save(destination/'contact_sheet.png')
    report = dict(pages=len(pages), encoding_errors=bad, characters_per_page=[len(p) for p in pages],
        keywords={v: text.count(v) for v in ('10/120', '120/120', '56', '77', '37', '48')},
        scope='Automated extraction/render only; visual inspection is separately recorded')
    (destination/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--pdf', type=Path, default=ROOT/'paper_v4/main.pdf')
    parser.add_argument('--out', type=Path, default=ROOT/'build_v4/pdf_qa_1')
    args = parser.parse_args()
    print(json.dumps(inspect(args.pdf, args.out), indent=2))
