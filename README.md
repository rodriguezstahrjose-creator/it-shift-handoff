# IT Shift Handoff — CMSC 495 Alpha

Solo capstone for Jose Rodriguez-Stahr. This extends the existing [private repository](https://github.com/rodriguezstahrjose-creator/it-shift-handoff), recovered at commit `ad1d2809412d83cf32a4dbbdf374c1c82baa6449`. It implements the shift handoff project from Units 1–3 using Python, Flask, SQLite, HTML/CSS/JavaScript, and local extractive TextRank.

The application keeps original shift notes, suggests source-linked sentences, lets a technician organize and supplement a draft, and requires explicit review before approval. It uses fictional training information only. No paid API, model download, live Navy records, ticket-system import, chatbot, or automatic distribution is involved.

## Run the project

Use Python **3.11 or newer**. First setup needs internet access to install the pinned packages. Later use is local and offline.

**Mac:** double-click `Start_Handoff.command`. If macOS opens it as text, open Terminal in this folder and run `bash Start_Handoff.command`.

**Windows:** install Python 3.11+ from python.org, then run `Start_Handoff.bat`. Windows launch instructions are provided; the Windows launcher has not been tested on Windows in this session.

The launcher creates an isolated `.venv`, initializes fictional demo notes, and prints a unique local demo password. Username: **technician**. Save the password from that first run. Open **http://127.0.0.1:5055** and keep the terminal open. Stop with Control-C. Reopening preserves notes and the existing password; it does not reset the account.

Manual setup (macOS/Linux):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m handoff init
.venv/bin/python -m handoff run
```

On Windows substitute `.venv\Scripts\python.exe` for `.venv/bin/python`. If port 5055 is occupied, use `python -m handoff run --port 5056` with the activated environment. A missing database must be initialized before running. The default database is `instance/handoff.sqlite` and is deliberately excluded from the release and Git history. To create a separate disposable demo without affecting existing records, set `HANDOFF_DATABASE` to a new database file before running `init` and `run`.

## Try the complete workflow

1. Sign in and select the fictional evening shift, or create a new shift.
2. Read the original notes. Add a fictional note if desired. Saved notes are immutable; corrections are additional notes.
3. Generate a suggested summary. The interface starts at **5 sentences**; 3, 8, and 10 are also available. The API's omitted `max_sentences` default remains 3, matching the earlier design contract.
4. Open **View source** to see the exact selected sentence highlighted in the full original note.
5. Assign every item to unresolved issues, completed troubleshooting, or pending actions. Use **Rewrite as technician** or **Add technician item** to supply missing context. Technician wording does not claim an extracted source.
6. Save the review. Confirm source checking and completeness, then approve.
7. The approved handoff becomes immutable. Reload it from **Saved drafts & handoffs**. Adding notes requires generating a new draft before a new approval.

An approved handoff records who approved it, when, its version, and the source revision. This solo prototype permits self-approval; it does not claim independent second-person authorization. If ranking fails or times out, original notes remain available and **Start a manual draft** is still usable.

## What is implemented

- Opaque server-side sessions, password hashing, sign-in throttling, inactivity expiry, and CSRF protection.
- Team-scoped shifts, immutable notes, revision tracking, and paginated retrieval.
- Local weighted sentence-graph TextRank in a separate process with a four-second timeout.
- Full source snapshots and exact Unicode code-point offsets; no silent dropping of notes.
- Technician additions, retained extraction history, version checks, atomic approval, and immutable approved records.
- Saved-draft/history selection, consistent errors, accessible labels, responsive layout, and plain-text rendering.
- Automated integration/security/failure-path tests and a GitHub Actions verification workflow.

## Verify it

```sh
python -m pip install -r requirements-dev.txt
python -m coverage run --source=handoff -m unittest discover -v
python -m coverage report --fail-under=85
python -m bandit -r handoff -ll
python -m compileall -q handoff scripts tests
python scripts/evaluate.py --output docs/evaluation-results.json
```

Use the virtual environment's Python. `requirements-dev.lock` records all installed runtime and development package versions for this build. `requirements.txt` pins the runtime dependencies. The CI workflow is in `.github/workflows/tests.yml` and uses Python 3.11 and 3.12 on Linux. **Hosted GitHub Actions execution has not been verified.** Local test evidence is included under `docs/evidence/`; this does not replace a successful hosted pipeline run required by Unit 5.

The final local verification passed 52 tests with 92% Python coverage. Coverage excludes execution inside the separate worker process, although integration tests invoke the real worker. Static scanning reported two low-severity subprocess warnings, analyzed in `docs/TECHNICAL_DEBT.md`; no medium/high findings were reported.

## Summary quality and limits

Twenty fictional scenarios are included: ten development cases and ten evaluation cases, with important sentence indices marked before running the evaluation. Both 3- and 5-sentence settings were measured without changing the ranking algorithm. On the ten evaluation cases, three sentences captured **16/30 (53.3%)** required items and five captured **24/30 (80.0%)**. Five was the preselected UI setting when the recovered cosine algorithm was reevaluated. The earlier reconstruction used a different similarity function; those earlier numbers are superseded by the included cosine results. These are small synthetic validation results, not independent operational validation or a guarantee that every handoff is complete. Future tuning needs fresh evaluation cases.

Three TextRank API requests at the exact 10,000-character, 200-sentence input boundary each took approximately **0.18 seconds** locally, including storage and worker startup, excluding browser/network latency. These measurements do not establish production throughput. See `docs/evaluation-results.json` for raw timings, environment metadata, selected sentences, and omissions.

Individual notes are limited to 5,000 characters; summary input to 10,000 total characters and 200 sentences. A draft has at most 30 items. Sentence splitting is heuristic, and TextRank ranks related wording rather than incident severity. Always read the original notes. The Alpha is a loopback-only development prototype; production deployment and 10,000 simultaneous users are outside scope.

## Project map

| Module | Responsibility |
| --- | --- |
| `handoff/auth.py` | Sign-in, server sessions, CSRF, expiry, throttling |
| `handoff/db.py`, `repository.py` | Schema, scoped queries, audit persistence |
| `handoff/services.py` | Note, summary, review, version, and approval rules |
| `handoff/textrank.py`, `rank_worker.py` | Source offsets, lexical graph, ranking, timeout |
| `handoff/routes.py`, `validation.py` | HTTP endpoints, strict input contracts |
| `handoff/static/`, `templates/` | Technician interface |
| `tests/test_workflow.py` | End-to-end API behavior and failure cases |
| `scripts/evaluate.py`, `data/scenarios.json` | Reproducible quality/performance evaluation |

See `docs/ARCHITECTURE.md`, `docs/API.md`, and `docs/PEER_REVIEW.md` for module review and testing guidance.

## GitHub and assignment status

This is an **Alpha branch of the original project**, not a completed Unit 5 submission. The original `handoff/store.py`, `demo.py`, original 20 tests, integration notes, and repository history are preserved. The browser worker uses the original cosine TextRank core, factored into a reusable function; sentence splitting now also recognizes newlines. The new authenticated web services extend the design with author metadata, paging, audit events, and a four-second worker timeout.

The original `Store` remains an internal compatibility/demo component with its original schema. The web application uses a separate enriched database schema; do not point `Store` at a web database. No legacy data migration is claimed. This transitional duplication is recorded in the technical-debt register.

Work is prepared on `feature/unit5-alpha` in the existing private repository. The original default branch and earlier PRs are preserved. Hosted checks must pass on the final Alpha commit before submission; use the branch/review link in the delivery message. Do not upload runtime databases, installed environments, or credentials.

The other independent student can review this ZIP without GitHub access. `docs/PEER_REVIEW.md` supplies the walkthrough and feedback form. No external peer feedback has been received or invented. The exactly 250-word refinement report must be completed **after** genuine feedback is received and the resulting changes are made. `docs/REFINEMENT_NOTES.txt` records what evidence to collect. Your own review of the other student's module is also still required.

## References and assistance

Mihalcea, R., & Tarau, P. (2004). TextRank: Bringing order into text. In *Proceedings of the 2004 Conference on Empirical Methods in Natural Language Processing* (pp. 404–411). Association for Computational Linguistics. https://aclanthology.org/W04-3252/

Pallets. (n.d.). *Testing Flask applications*. Flask documentation. https://flask.palletsprojects.com/en/stable/testing/

The implementation follows the previously prepared Unit 3 shift handoff design. Development, documentation, synthetic examples, and automated verification were prepared with Codex assistance. The earlier local reconstruction history is not substituted for the original GitHub history. Review and understand the implementation before presenting it as your capstone; record assistance according to your course's actual requirements.
