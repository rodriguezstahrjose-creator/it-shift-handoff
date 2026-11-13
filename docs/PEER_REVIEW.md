# Independent-student review package

This is Jose's solo IT Shift Handoff Alpha. The core application is ready for another independent student to inspect and try. **Feedback has not yet been received.** Please record what you actually observe rather than checking every area as passed by default.

## Start here

1. Unzip the project and follow the README launch steps. First setup installs dependencies; later runs operate locally. The generated demo credentials belong to your own local copy.
2. Sign in and choose the fictional evening shift. Read the original notes.
3. Generate five suggested sentences. Open a source link and confirm that the selected sentence is highlighted in the original note.
4. Categorize the suggestions. Add a missing next step as a technician item. Save; confirm the two review checks; approve.
5. Reload and select the same shift and approved handoff from history. Confirm that editing is unavailable.
6. Generate a new draft, then add another note. Try saving/approving the earlier draft: the server should reject the changed source snapshot.
7. Run the automated tests if practical. Test accounts, records, and notes are fictional and isolated in temporary databases.
8. Try the brief urgent-action and abbreviation fixtures in `data/review-stress-cases.json`. Record each missed critical item, even if the overall evaluation reaches 80%. Check whether a technician can find and restore the missing action before approval.

## Suggested bounded module to review

Start with `handoff/services.py`, specifically `SummaryService` and `HandoffService`. Follow the corresponding scoped persistence in `repository.py`, request contracts in `validation.py`, and API tests in `tests/test_workflow.py`. Review other modules if useful; no reviewer ownership is assumed in advance.

| Required area | Questions to investigate |
| --- | --- |
| Code quality/readability | Are the service responsibilities clear? Are approval rules understandable? Are names and error messages consistent? |
| Security | Can unauthenticated or other-team users reach records? Can extracted sources be forged? Are CSRF, plaintext rendering, and session rotation handled? |
| Performance | Is ranking bounded? Are transactions short? Could the full summary history or source snapshots grow too much? |
| Integration compatibility | Do routes, services, repository snapshots, and UI agree on version/source fields? Does a storage/ranker failure leave the workflow honest? |
| Documentation | Can you run it from a clean checkout? Do the API guide, module map, limits, and test evidence match the observed behavior? |

## Feedback form — to be completed by the actual reviewer

- Reviewer name:
- Date:
- Version/commit or ZIP reviewed:
- Module(s) inspected:
- Environment and setup outcome:
- Commands or scenarios tried:

For each finding, record:

| Field | Reviewer response |
| --- | --- |
| Finding ID / severity | |
| Required area | readability / security / performance / integration / documentation |
| File and function | |
| Steps to reproduce or code evidence | |
| Expected behavior | |
| Actual behavior | |
| Suggested change | |
| Reliability/technical-debt impact | |

Please include strengths and limitations even if you find no blocking issue. Do not equate a passing test with independent proof that every case is covered.

## Jose's response log — complete after feedback arrives

| Finding | Accepted/deferred and reason | Specific change | Verification | Commit |
| --- | --- | --- | --- | --- |
| Pending external feedback | | | | |

The 250-word report comes after these observations and changes. This review pack is not a substitute for the student's own formal review of the other independent student's module. Use the same five-area form when you perform that separate review, recording their actual code and your findings.
