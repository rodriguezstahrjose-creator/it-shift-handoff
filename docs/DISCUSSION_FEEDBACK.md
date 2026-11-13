# Discussion feedback reviewed for the Alpha

Reviewed November 13, 2026. These are genuine course discussion comments, not formal reviews of this Alpha's source code. Formal independent-student module review remains pending.

## Unit 1: privacy and oversight

Source: [The Workforce Solution Pitch — Jose Rodriguez-Stahr](https://learn.umgc.edu/d2l/le/1541054/discussions/threads/38742555/View).

**Merrill Davis, October 18:** restrict sensitive details to authorized people and have a person check summaries before sharing.

**Dylan Seidlitz, October 28:** consider role-based viewing privileges and an explicit human accuracy-review confirmation.

Alpha response: authenticated, team-scoped resource checks protect notes and summaries; server-side sessions and CSRF guard mutations; source review and completeness confirmations are required before approval. No automatic sharing is implemented. Existing tests check other-team rejection, unsigned-in rejection, CSRF, and approval requirements.

Per-note classification and multiple privilege roles are **not** implemented. The earlier solo MVP specified one technician role and fictional notes. A team boundary is not equivalent to a clearance/classification system; real sensitive operational use would require a separate access model and review. This suggestion is retained as future work rather than claimed complete.

## Unit 2: omissions and realistic evaluation

Source: [Week 2 Jose Rodriguez-Stahr](https://learn.umgc.edu/d2l/le/1541054/discussions/threads/38818785/View).

**Dylan Whitney, October 27:** test a short urgent pending action and verify that a technician can find and restore it if TextRank omits it. Compare parameter changes with improvements to human source review.

**Shalom Olukunle, October 27:** test different note formats, abbreviations, and incomplete troubleshooting; do not let an overall 80% score hide critical failures in individual handoffs.

Alpha response: preserve per-scenario omissions in the evaluation JSON and verification table; retain the poor three-sentence result; recommend five while still requiring source review. New stress fixtures cover a terse urgent action among repeated low-priority notes, abbreviations, incomplete troubleshooting, and a critical action in a second note. A workflow regression checks each stress case's original notes remain accessible, the missing action can be added as technician wording, and approval persists that addition. This demonstrates recovery; it does **not** assert that TextRank captures every critical action. The original evaluation set and results remain unchanged.

The reviewer checklist now explicitly asks for missed critical actions and per-case outcomes. Increasing summary length is a limited mitigation, not a replacement for review. There is no automatic severity classifier or assertion of operational safety.

## Unit 4: regression tests and review gate

Source: [Week 4 Jose Rodriguez-Stahr](https://learn.umgc.edu/d2l/le/1541054/discussions/threads/38961470/View).

**Jordan Leach, November 8:** require regression tests for old issues in each pull request and keep a checklist covering source validation, outdated drafts, and technician approval.

Alpha response: added `.github/pull_request_template.md` with those checks plus a complete workflow verification requirement. Added an explicit cross-draft reference-transfer regression, corresponding to the failure described in Jose's Week 4 post. Existing tests cover source tampering, stale draft/source revisions, confirmation requirements, immutable approvals, persistence, timeouts, and rollback. The CI workflow runs the complete regression suite and enforces an 85% coverage threshold plus a medium/high security gate. Hosted execution and branch-protection settings cannot be claimed from local tests.

## Original Unit 4 repository recovered

The signed-in browser recovered the original private repository, `rodriguezstahrjose-creator/it-shift-handoff`, at main commit `ad1d2809412d83cf32a4dbbdf374c1c82baa6449`. Its Store, demo, 20 original tests, and integration record are retained. The browser worker now shares the original cosine ranking core, and the complete combined suite has 52 tests. Updates are prepared on a separate `feature/unit5-alpha` branch so the earlier history is preserved. Discussion input still does not constitute formal independent review of this source code.
