"""Run a fictional-data source -> review -> approval integration demonstration."""

from copy import deepcopy
from handoff.store import Store, RuleError, uid


def main():
    store = Store()
    try:
        shift = store.create_shift("fictional-team", "Demo night shift")["id"]
        store.add_note("fictional-team", shift, "Printer A disconnects. Reinstalled driver. Pending: check cable.")
        draft = store.generate("fictional-team", shift)
        print("Generated source-linked draft:")
        for item in draft["items"]:
            print(" -", item["text"])

        changed = deepcopy(draft["items"])
        changed[0]["text"] = "Printer is repaired."
        try:
            store.save_review("fictional-team", draft["id"], 1, changed)
        except RuleError as error:
            print("Rewriting extracted text correctly blocked:", error)

        reviewed = deepcopy(draft["items"])
        for item, category in zip(reviewed, ["unresolved", "completed", "pending"]):
            item["category"] = category
        reviewed.append({"item_id": uid(), "origin": "technician", "text": "Check spare cable during next shift.",
                         "category": "pending", "source_sentence_id": None})
        draft = store.save_review("fictional-team", draft["id"], 1, reviewed)
        store.add_note("fictional-team", shift, "New note: replacement cable has arrived.")
        try:
            store.approve("fictional-team", draft["id"], draft["version"], "demo-technician", True, True)
        except RuleError as error:
            print("Approval after source change correctly blocked:", error)

        # Re-extract from the new snapshot. Old extraction IDs belong only to
        # their original draft and must not be copied into a fresh draft.
        fresh = store.generate("fictional-team", shift, max_sentences=10)
        fresh_items = deepcopy(fresh["items"])
        for item, category in zip(fresh_items, ["unresolved", "completed", "pending", "pending"]):
            item["category"] = category
        fresh = store.save_review("fictional-team", fresh["id"], 1, fresh_items)
        approved = store.approve("fictional-team", fresh["id"], fresh["version"], "demo-technician", True, True)
        print("Final status:", approved["status"])
    finally:
        store.close()


if __name__ == "__main__":
    main()
