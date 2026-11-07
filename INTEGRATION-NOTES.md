# First local integration checkpoint

Date: November 7, 2026 (America/New_York)

## Completed increments

1. Initialized main with the fictional-data scope.
2. Developed feature/source-linked-summaries: SQLite notes and source snapshots,
   TextRank extraction, source offsets, and seven passing tests; merged locally.
3. Developed feature/technician-review: review and approval rules, a demo,
   regression tests, and a prepared GitHub Actions workflow; tested before merge.

## Actual failure and fix

The first combined run passed the then-current 18 unit/service tests, but the
demo failed. After demonstrating stale-source rejection, its recovery path
created a fresh manual draft and copied reviewed extraction items from the old
draft. Those IDs were not part of the new draft's original extraction, so
save_review raised INVALID_SOURCE. This was a demo integration error; the source
validator was correctly enforcing the Unit 3 contract.

The corrected recovery generates a fresh TextRank draft from the updated note
snapshot and categorizes its newly extracted items before requesting approval.
Manual drafts must instead contain technician-origin items with null source
references. The manual fallback is separately tested.

Two regression checks were added: old extraction IDs cannot be transferred to a
new draft, and the complete demonstration must reach approval. Final result:
20 tests pass; the demo ends with `Final status: approved`.

## Relevant earlier peer feedback

In the Week 2 discussion, Dylan Whitney suggested testing a short urgent pending
action that TextRank might omit. Shalom Olukunle suggested testing varied note
formats and considering omissions per scenario even when aggregate quality
meets the proposed target. This is actual discussion feedback, not repository
code review. It motivates preserving source notes, technician additions, and
manual approval. A representative held-out summary-quality evaluation is still
future work; these integration tests do not establish that target.

## AI assistance and review status

Codex generated the initial implementation, tests, demo, and documentation, and
ran the checks. It compared the behavior with the Unit 3 source-provenance and
approval rules. There was no teammate contribution or independent human code
review. Jose should read the code and run the demo before describing a personal
review as complete.

Proposed human review policy: understand AI-generated changes; check requirements
and source attribution; inspect failure and boundary cases; run unit and
integration tests; document AI assistance; merge only once these checks pass.
AI assistance does not provide an independent reviewer.

## Local versus hosted status

These are real local Git branches and merges. They are not GitHub pull requests.
The GitHub Actions configuration has not executed on GitHub, and no remote branch
protection exists yet. Repository publication requires GitHub access. The full
Flask application, authentication, browser interface, hard process timeout, and
representative quality/performance evaluation remain outside this increment.
