from copy import deepcopy
import unittest

from handoff.store import Store, RuleError, uid


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.shift = self.store.create_shift("demo-team", "Fictional shift")["id"]
        self.store.add_note("demo-team", self.shift,
                            "Router is offline. Restart did not help. Pending: check cable.")
        self.draft = self.store.generate("demo-team", self.shift)

    def ready(self):
        items = deepcopy(self.draft["items"])
        for item in items:
            item["category"] = "pending"
        return self.store.save_review("demo-team", self.draft["id"], 1, items)

    def approve(self, draft, **options):
        return self.store.approve("demo-team", draft["id"], draft["version"],
                                  "fictional-technician", **options)

    def test_extracted_wording_cannot_be_overwritten(self):
        items = deepcopy(self.draft["items"])
        items[0]["text"] = "Everything is resolved."
        with self.assertRaisesRegex(RuleError, "INVALID_SOURCE"):
            self.store.save_review("demo-team", self.draft["id"], 1, items)
        self.assertEqual(self.store.summary("demo-team", self.draft["id"])["version"], 1)

    def test_source_id_cannot_be_forged(self):
        items = deepcopy(self.draft["items"])
        items[0]["source_sentence_id"] = uid()
        with self.assertRaisesRegex(RuleError, "INVALID_SOURCE"):
            self.store.save_review("demo-team", self.draft["id"], 1, items)

    def test_rewrite_as_technician_addition_preserves_extraction_history(self):
        items = deepcopy(self.draft["items"])[1:]
        items.append({"item_id": uid(), "origin": "technician", "text": "Check router cable next shift.",
                      "source_sentence_id": None, "category": "pending"})
        saved = self.store.save_review("demo-team", self.draft["id"], 1, items)
        self.assertEqual(saved["original_items"], self.draft["original_items"])
        self.assertEqual(saved["items"][-1]["origin"], "technician")

    def test_technician_cannot_claim_extracted_source_or_reuse_extraction_id(self):
        for source_id, item_id in ((uid(), uid()), (None, self.draft["items"][0]["item_id"])):
            item = {"item_id": item_id, "origin": "technician", "text": "Added detail.",
                    "source_sentence_id": source_id, "category": "pending"}
            with self.assertRaisesRegex(RuleError, "INVALID_SOURCE"):
                self.store.save_review("demo-team", self.draft["id"], 1, [item])

    def test_new_notes_block_approval_and_require_fresh_draft(self):
        draft = self.ready()
        self.store.add_note("demo-team", self.shift, "New urgent pending action: inspect switch.")
        with self.assertRaisesRegex(RuleError, "SOURCE_CHANGED"):
            self.approve(draft, source_review_confirmed=True, completeness_confirmed=True)
        self.assertEqual(self.store.summary("demo-team", draft["id"])["status"], "draft")

    def test_missing_confirmations_categories_and_empty_items_block_approval(self):
        with self.assertRaisesRegex(RuleError, "REVIEW_INCOMPLETE"):
            self.approve(self.draft, source_review_confirmed=True, completeness_confirmed=True)
        draft = self.ready()
        with self.assertRaisesRegex(RuleError, "REVIEW_INCOMPLETE"):
            self.approve(draft)
        draft = self.store.save_review("demo-team", draft["id"], draft["version"], [])
        with self.assertRaisesRegex(RuleError, "REVIEW_INCOMPLETE"):
            self.approve(draft, source_review_confirmed=True, completeness_confirmed=True)

    def test_stale_review_is_rejected(self):
        self.ready()
        with self.assertRaisesRegex(RuleError, "VERSION_CONFLICT"):
            self.store.save_review("demo-team", self.draft["id"], 1, self.draft["items"])

    def test_same_review_save_does_not_increment_version(self):
        draft = self.ready()
        repeated = self.store.save_review("demo-team", draft["id"], draft["version"], draft["items"])
        self.assertEqual(repeated["version"], draft["version"])

    def test_approval_persists_identity_and_time_and_is_immutable(self):
        draft = self.ready()
        approved = self.approve(draft, source_review_confirmed=True, completeness_confirmed=True)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approval"]["approved_by"], "fictional-technician")
        self.assertTrue(approved["approval"]["approved_at"])
        with self.assertRaisesRegex(RuleError, "ALREADY_APPROVED"):
            self.store.save_review("demo-team", draft["id"], approved["version"], [])
        repeated = self.approve(draft, source_review_confirmed=True, completeness_confirmed=True)
        self.assertEqual(repeated["approval"], approved["approval"])

    def test_full_manual_fallback_flow(self):
        draft = self.store.generate("demo-team", self.shift, mode="manual")
        item = {"item_id": uid(), "origin": "technician", "text": "Inspect the router cable.",
                "source_sentence_id": None, "category": "pending"}
        draft = self.store.save_review("demo-team", draft["id"], 1, [item])
        approved = self.approve(draft, source_review_confirmed=True, completeness_confirmed=True)
        self.assertEqual(approved["items"][0]["origin"], "technician")
        self.assertEqual(len(approved["original_items"]), 0)

    def test_other_team_cannot_review_or_approve(self):
        with self.assertRaisesRegex(RuleError, "NOT_FOUND"):
            self.store.save_review("other-team", self.draft["id"], 1, [])
        with self.assertRaisesRegex(RuleError, "NOT_FOUND"):
            self.store.approve("other-team", self.draft["id"], 1, "a", True, True)

    def test_extraction_ids_cannot_transfer_to_a_new_draft(self):
        old = self.ready()
        self.store.add_note("demo-team", self.shift, "Pending: check switch too.")
        fresh = self.store.generate("demo-team", self.shift, max_sentences=10)
        with self.assertRaisesRegex(RuleError, "INVALID_SOURCE"):
            self.store.save_review("demo-team", fresh["id"], 1, old["items"])
        for item in fresh["items"]:
            item["category"] = "pending"
        fresh = self.store.save_review("demo-team", fresh["id"], 1, fresh["items"])
        approved = self.approve(fresh, source_review_confirmed=True, completeness_confirmed=True)
        self.assertEqual(len(approved["source_note_ids"]), 2)


class DemoIntegrationTests(unittest.TestCase):
    def test_complete_demo_reaches_approval(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from demo import main
        output = StringIO()
        with redirect_stdout(output):
            main()
        self.assertIn("Final status: approved", output.getvalue())
        self.assertIn("SOURCE_CHANGED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
