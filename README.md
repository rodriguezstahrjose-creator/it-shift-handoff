# IT shift handoff prototype

Initial backend component for Jose's CMSC 495 project. Uses fictional data only.
Python 3.11+; no third-party dependencies. This increment establishes the core
workflow before Flask routes, authentication, and a browser interface are added.

## Scope

Local TextRank extracts source sentences. A technician supplies categories and
additional details, then explicitly approves the handoff. It does not import
operational records or distribute handoffs. It is not ready for operational use.

## Run

From this directory, with Python 3.11 or newer:

```text
python -m unittest discover -v
python demo.py
```

The demo uses an in-memory SQLite database and fictional printer notes. It shows
source extraction, rejection of altered extraction text, rejection of approval
after new notes arrive, fresh extraction, review, and explicit approval.

## What is implemented

- SQLite shifts, immutable note entry, draft snapshots, and approval records.
- Local TextRank using cosine sentence similarity and damped graph ranking.
- Exact source offsets and original extraction history.
- Separate technician additions and categorization.
- Version checks, stale-source rejection, confirmation requirements, immutable
  approvals, and idempotent retries for the same approval request.
- A manual draft path; fictional cross-team boundary checks.
- Automated source, review, persistence, and integration tests.
- A GitHub Actions workflow prepared for a future hosted repository.

## Boundaries of this increment

This is a backend component, not the complete Flask application. Authentication,
HTTP routes, browser forms, CSRF controls, deployment, security scanning, and
enforced branch protection are not implemented. Team and technician identifiers
are trusted caller inputs in this local component; production must derive them
from authenticated sessions. SQL uses parameters, but this is not a security
audit. The full Unit 3 API contract is not yet implemented.

The demo and automated checks do not establish the 80% information-capture target
or five-second performance target on a representative held-out dataset. The
ranking loop has bounded iterations and input limits, but the planned hard
four-second child-process timeout is not implemented.

## Branch and review workflow

Use short-lived feature branches, inspect the diff against the Unit 3 contracts,
run the tests and demo, then merge into main. Local merge commits preserve the
two completed increments. Both increments were subsequently published and merged
through GitHub pull requests:

- [Source-linked summaries, PR #1](https://github.com/rodriguezstahrjose-creator/it-shift-handoff/pull/1)
- [Technician review and quality checks, PR #2](https://github.com/rodriguezstahrjose-creator/it-shift-handoff/pull/2)

PR #2 passed both push and pull-request checks before merging. The hosted test
log records 20 passing tests; the demo step also succeeded. Branch protection
is not configured, so checks run automatically but are not an enforced merge rule.

AI-generated code and tests require human understanding and review. Expected
results must come from the design requirements, rather than accepting whatever
the implementation produces. Review source provenance, failure cases, input
limits, and dependencies before merging. No actual Navy records belong here.

The initial implementation and automated checks were created with Codex. There
was no independent human code review or teammate approval.
