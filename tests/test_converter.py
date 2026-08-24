import csv
import json
import tempfile
import unittest
from pathlib import Path

from enpass_to_1password import ConversionError, convert, load_export


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "all_categories.json"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ConverterTests(unittest.TestCase):
    def test_all_items_are_written_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            report = convert(FIXTURE, output)
            self.assertEqual(report["source_items"], 5)
            self.assertEqual(report["output_items"], {
                "logins": 1,
                "credit_cards": 1,
                "secure_notes": 3,
            })
            total = sum(len(read_csv(output / f"{name}.csv")) for name in report["output_items"])
            self.assertEqual(total, report["source_items"])

    def test_csv_quoting_unicode_and_multiline_values_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            convert(FIXTURE, output)
            login = read_csv(output / "logins.csv")[0]
            self.assertEqual(login["Title"], "Example, Login")
            self.assertEqual(login["Password"], 'p,a"ss')
            self.assertIn("Line one\nLine two", login["Notes"])
            self.assertEqual(login["One-time password"], "otpauth://totp/Example?secret=TEST")

    def test_unsupported_and_incomplete_items_become_secure_notes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            report = convert(FIXTURE, output)
            notes = {row["Title"]: row for row in read_csv(output / "secure_notes.csv")}
            self.assertIn("Identity", notes)
            self.assertIn("Incomplete Login", notes)
            self.assertIn("Software License", notes)
            self.assertIn("only-password", notes["Incomplete Login"]["Notes"])
            self.assertEqual(report["downgraded_to_secure_note"], 3)

    def test_attachments_are_extracted_without_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            report = convert(FIXTURE, output)
            self.assertEqual(report["attachments_extracted"], 1)
            extracted = list((output / "attachments").iterdir())
            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0].read_bytes(), b"synthetic test data")
            self.assertEqual(extracted[0].parent.resolve(), (output / "attachments").resolve())

    def test_output_is_utf8_with_bom_for_windows_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            convert(FIXTURE, output)
            self.assertTrue((output / "logins.csv").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_non_empty_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            (output / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ConversionError):
                convert(FIXTURE, output)
            self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_invalid_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text(json.dumps([]), encoding="utf-8")
            with self.assertRaises(ConversionError):
                load_export(path)


if __name__ == "__main__":
    unittest.main()

