import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.v4 import inventory
from scripts.v4.common import sha256
from scripts.v4.relocation import RECEIPT


class RelocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paper, self.out = root / "paper", root / "out"
        self.paper.mkdir()
        (self.out / "manifests").mkdir(parents=True)
        self.data = b"retired release"
        self.expected = dict(sha256=hashlib.sha256(self.data).hexdigest(), bytes=len(self.data))
        self.original = self.out / "manifests/historical_hashes.json"
        self.original.write_text(json.dumps(dict(files={"dist/v2.zip": self.expected})), encoding="utf-8")
        self.archive = root / "history.zip"
        with zipfile.ZipFile(self.archive, "w") as z:
            z.writestr("old/v2.zip", self.data)
        self.entry = dict(self.expected, archive=str(self.archive), entry="old/v2.zip")
        self.receipt = dict(original_protection_manifest_sha256=sha256(self.original),
                            files={"dist/v2.zip": self.entry})
        for name, value in (("PAPER", self.paper), ("OUT", self.out)):
            p = patch.object(inventory, name, value)
            p.start()
            self.addCleanup(p.stop)

    def write_receipt(self):
        (self.out / RECEIPT).write_text(json.dumps(self.receipt), encoding="utf-8")

    def test_verified_relocation_is_explicit(self):
        self.write_receipt()
        result = inventory.verify_protection()
        self.assertEqual(result["protection"], "PASS_WITH_AUTHORIZED_RELOCATION")
        self.assertEqual(result["authorized_archived_files"], ["dist/v2.zip"])

    def test_missing_without_receipt_fails(self):
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_missing_archive_fails(self):
        self.write_receipt()
        self.archive.unlink()
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_wrong_archive_contents_fail(self):
        self.write_receipt()
        with zipfile.ZipFile(self.archive, "w") as z:
            z.writestr("old/v2.zip", b"changed release")
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_corrupt_archive_fails(self):
        self.write_receipt()
        self.archive.write_bytes(b'corrupt')
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_receipt_cannot_rebaseline(self):
        self.receipt["files"]["dist/v2.zip"]["sha256"] = "0" * 64
        self.write_receipt()
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_modified_original_manifest_fails(self):
        self.write_receipt()
        self.original.write_text('{"files": {}}', encoding="utf-8")
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_changed_current_file_not_excused_by_archive(self):
        self.write_receipt()
        (self.paper / "dist").mkdir()
        (self.paper / "dist/v2.zip").write_bytes(b"different")
        with self.assertRaises(RuntimeError):
            inventory.verify_protection()

    def test_present_identical_is_in_place_pass(self):
        (self.paper / "dist").mkdir()
        (self.paper / "dist/v2.zip").write_bytes(self.data)
        self.assertEqual(inventory.verify_protection()["protection"], "PASS")


if __name__ == "__main__":
    unittest.main()
