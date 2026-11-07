import tempfile
import unittest
from pathlib import Path

from handoff.ranking import extract
from handoff.store import Store, RuleError


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.shift = self.store.create_shift("fictional-team", "Fictional night shift")["id"]

    def test_source_offsets_preserve_unicode_and_whitespace(self):
        note = {"id": "fictional-note", "text": "  Router café is offline.\n Pending: check cable!  "}
        selected = extract([note], 2)
        self.assertEqual(len(selected), 2)
        for source in selected:
            self.assertEqual(source["text"], note["text"][source["start"]:source["end"]])
            self.assertEqual(source["note_id"], note["id"])

    def test_extract_never_creates_new_wording(self):
        notes = [{"id": "a", "text": "Printer failed. Driver reinstall failed. Pending: replace cable."}]
        selected = extract(notes, 2)
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(s["text"] in notes[0]["text"] for s in selected))

    def test_disconnected_sentences_have_deterministic_ties(self):
        notes = [{"id": "a", "text": "Alpha. Beta. Gamma."}]
        self.assertEqual([s["text"] for s in extract(notes, 2)], ["Alpha.", "Beta."])

    def test_draft_records_snapshot_and_does_not_auto_categorize(self):
        note_id = self.store.add_note("fictional-team", self.shift, "Printer is offline.")
        draft = self.store.generate("fictional-team", self.shift)
        self.assertEqual(draft["source_note_ids"], [note_id])
        self.assertEqual(draft["source_revision"], 2)
        self.assertEqual(draft["status"], "draft")
        self.assertIsNone(draft["approval"])
        self.assertEqual(draft["items"][0]["category"], "unassigned")

    def test_empty_oversized_and_other_team_inputs_rejected(self):
        with self.assertRaisesRegex(RuleError, "NO_NOTES"):
            self.store.generate("fictional-team", self.shift)
        for text in ("  ", "a" * 5001):
            with self.assertRaisesRegex(RuleError, "VALIDATION_ERROR"):
                self.store.add_note("fictional-team", self.shift, text)
        with self.assertRaisesRegex(RuleError, "NOT_FOUND"):
            self.store.notes("different-team", self.shift)

    def test_manual_and_automatic_modes_both_enforce_snapshot_limit(self):
        for _ in range(3):
            self.store.add_note("fictional-team", self.shift, "a" * 4000)
        for mode in ("manual", "textrank"):
            with self.assertRaisesRegex(RuleError, "INPUT_LIMIT_EXCEEDED"):
                self.store.generate("fictional-team", self.shift, mode)

    def test_sqlite_records_survive_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "fictional.db")
            first = Store(path)
            try:
                shift = first.create_shift("a", "Demo")["id"]
                first.add_note("a", shift, "Demo note.")
                draft = first.generate("a", shift)
            finally:
                first.close()
            second = Store(path)
            try:
                self.assertEqual(second.summary("a", draft["id"])["items"], draft["items"])
            finally:
                second.close()


if __name__ == "__main__":
    unittest.main()
