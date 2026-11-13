# Technical debt and Alpha limitations

This register is based on implementation and self-testing, not external peer feedback. The project is a solo local prototype, and these items must not be described as peer-requested changes in the later refinement report.

| ID | Concrete shortcut or limitation | Reliability/maintenance impact | Current mitigation | Next improvement and verification |
| --- | --- | --- | --- | --- |
| TD-01 | Cosine-similarity TextRank favors repeated topics. In evaluation case 09, an isolated UPS alarm competes with several portal-layout sentences. | Important, less-repeated incidents may be omitted. Three suggestions captured only 16/30 marked items. | UI starts at five suggestions (24/30 captured in the same synthetic evaluation), exact source links, manual additions, and mandatory approval confirmations. This does not eliminate omissions. | Add coverage-aware selection and more varied fresh reference cases; independently label key items and measure omissions before adoption. Keep baseline results unchanged. |
| TD-02 | Regex sentence splitting instead of a full NLP sentence segmenter. | Abbreviations, decimals, and unusual punctuation can split or join sentences incorrectly. | Exact saved source offsets, sentence bounds, and human source review. | Add abbreviation/decimal test fixtures and evaluate a segmenter against fresh cases, preserving Unicode offsets and offline operation. |
| TD-03 | Summary snapshots and item history use JSON columns without schema migrations. | Future contract changes could leave old drafts unreadable or require manual conversion. | Algorithm version recorded; current data contracts validated; original extraction and review events retained. | Add explicit schema versioning, migration scripts, and backup/restore round-trip tests before a second persisted schema. |
| TD-04 | SQLite and one in-process ranking lock. | Only one writer at a time; admission control does not span multiple app processes. | Short transactional writes, four-second worker deadline, WAL, and an explicit single-instance local scope. | If deployment expands, measure a realistic concurrent workload, add shared admission control/queue, then evaluate PostgreSQL only if needed. No 10,000-user claim. |
| TD-05 | Sessions are expired on access; no periodic session cleanup. Login throttling is a local username/address counter. | Old sessions can accumulate; distributed or concurrent attackers need stronger throttling. | Random token hashes, server-side expiry, session rotation, CSRF, and loopback-only use. | Add maintenance cleanup, bounded retention, transactional rate-limit counters, and load/race tests before public hosting. |
| TD-06 | Browser testing was performed manually through the desktop browser; CI automates Python tests only. | Future JavaScript changes could regress UI behavior despite passing API tests. | Verified sign-in, source highlighting, categories, technician additions, save, approval, and persisted history in this build. | Add a supported browser-test job covering the same workflow and narrow-screen interaction. Mobile/Windows behavior is not claimed as tested here. |
| TD-07 | Original GitHub Actions workflow extended through a signed-in browser; final Alpha hosted run pending. | A remote dependency/platform issue may still prevent hosted checks from passing. | All configured commands pass locally with pinned versions; earlier repository history is preserved on the separate Alpha branch. | Verify Python 3.11/3.12 matrix results, and record the run URL + commit before submission. |

## Static security scan review

Bandit reported **two LOW-severity warnings**, B404 and B603, for importing and invoking `subprocess` in `handoff/textrank.py`. The invocation uses the running Python executable and a fixed local worker path, with `shell=False` (default), a fixed argument list, bounded input, and a timeout. Notes are passed through stdin, not command arguments. No shell command is constructed from user content. These warnings remain visible in the full scan evidence; the CI gate blocks medium and high findings with `-ll`. This is analysis of the two warnings, not proof that the application has no security flaws.

## Self-test refinements actually made

- The interface initially offered three sentences by default. After measuring both predetermined settings, the default UI selection was changed to five; the API retains the design's three-sentence default. The selection of the UI setting uses these validation results, so fresh cases are needed for a future independent test.
- Non-ASCII CSRF headers now return a controlled 403 instead of reaching `compare_digest` with an unsupported value. An automated regression case checks it.
- Summary generation blocks switching shifts until completion; stale asynchronous list results are ignored if the selected shift changed.
- Saving a note clears the input only if its text still matches what was submitted, preserving text added while the request was in flight.
- Source highlighting converts JavaScript strings to Unicode code points before slicing; this keeps Python source offsets correct when notes contain emoji or other supplementary characters.

These changes are attributable to development/testing. External review findings and the resulting fixes must be added separately, with real reviewer evidence.

## Compatibility-layer debt (TD-08)

The recovered Store supports the original internal API and demo with its original database schema. The new authenticated web services use an enriched schema. Retaining both avoids breaking the original 20 tests and demonstrates continuity, but duplicates workflow logic and increases maintenance cost. The web worker and CLI share the original cosine ranking implementation, and both test suites run together. Do not share database files between these schemas. Next: consolidate persistence behind one adapter, add an explicit schema migration, and keep all existing contract and regression tests passing. No migration or existing-record compatibility is claimed in this Alpha.
