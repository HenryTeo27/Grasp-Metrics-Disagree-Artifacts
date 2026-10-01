"""Check the public payload and untouched scientific package, without imports."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def verify(root, manifest):
    count = 0
    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        expected, relative = line.split("  ", 1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise RuntimeError("Missing or unsafe path: " + relative)
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError("Hash mismatch: " + relative)
        count += 1
    return count


if __name__ == "__main__":
    total = verify(ROOT, ROOT / "MANIFEST.sha256")
    frozen = verify(ROOT / "evidence", ROOT / "evidence/MANIFEST.sha256")
    print(f"PASS: {total} public payload files; {frozen} frozen evidence files.")
