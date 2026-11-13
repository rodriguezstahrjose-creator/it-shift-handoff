# Verification record

Local verification performed November 13, 2026. These are actual local results, not a hosted GitHub Actions run or an external peer review.

## Automated checks

- 52 tests passed (see evidence/unit-tests.txt).
- Python statement coverage: 92%, including the application and CLI; separate child-process execution is not counted by this coverage run.
- Bandit: no medium/high findings; two low-severity subprocess warnings retained and assessed in TECHNICAL_DEBT.md.
- Python compilation, JavaScript syntax, and Mac launcher shell syntax passed.
- Linux CI matrix is configured for Python 3.11 and 3.12, but has not yet run on GitHub.

## Quality and performance

Environment: macOS-26.5.1-arm64-arm-64bit; Python 3.12.14; architecture arm64.

| Evaluation scenario | Required captured (3 sentences) | Required captured (5 sentences) | Omitted indices at 5 |
| --- | --- | --- | --- |
| eval-01-mail | 2/3 | 3/3 | [] |
| eval-02-vpn | 2/3 | 3/3 | [] |
| eval-03-disk | 2/3 | 3/3 | [] |
| eval-04-resolved | 2/3 | 3/3 | [] |
| eval-05-queue | 2/3 | 3/3 | [] |
| eval-06-split-notes | 2/3 | 3/3 | [] |
| eval-07-maintenance | 2/3 | 3/3 | [] |
| eval-08-multiple-incidents | 2/3 | 2/3 | [1] |
| eval-09-isolated-critical | 0/3 | 1/3 | [5, 6] |
| eval-10-longer-handoff | 0/3 | 0/3 | [3, 4, 5] |

Overall: 16/30 (53.3%) at 3 sentences; 24/30 (80.0%) at 5. The UI now starts at five. This setting was selected after the comparison, so future tuning should use new cases. Reference items are author-defined synthetic labels; this is not blinded or independently validated research.

Three full summary POSTs at the exact 10,000-character/200-sentence boundary took 0.1766s, 0.1780s, 0.1783s. Each returned 201. These are Flask test-client times including storage and worker startup, excluding network and browser rendering. The planned five-second single-request target was met locally; no production throughput claim is made.

## Browser verification

Verified in the desktop in-app browser at 1280-pixel width:

- Sign in with a generated local demo account.
- Retrieve fictional notes and create a new shift and note.
- Generate a real TextRank draft and inspect exact source-note highlighting.
- Categorize suggestions and save an additional technician-authored action.
- Approval remains disabled until saved, categorized, and both confirmations checked.
- Approve, restart the server, reload the page, and retrieve the immutable approved handoff from history.
- Viewport content width equals 1280; no horizontal overflow in the observed desktop state.
- Emoji/Unicode source highlighting was checked separately after converting client slices to code-point indexing.

The full approved workflow screenshot is evidence/approved-workflow.png. Browser behavior was checked manually; no automated browser regression suite is included yet. Narrow-screen and Windows launcher testing remain pending.

## Remaining assignment work

1. Verify the final Alpha branch in the recovered original repository; record the actual run URL and commit.
2. Obtain genuine feedback from another independent student and perform your own formal review of their module.
3. Implement and verify accepted feedback changes, update the debt log, and write the exactly 250-word refinement report.

## Discussion-driven additions

After reviewing actual replies, added the pull request quality-gate template, critical-action/abbreviation stress fixtures, and two new regression tests covering cross-draft reference transfer and technician recovery of critical actions. All 52 tests pass. The original synthetic quality results were retained rather than retuned. These discussion comments do not constitute a formal source-code peer review.

The original repository was recovered at commit ad1d2809412d83cf32a4dbbdf374c1c82baa6449. Its original 20 tests and demo pass together with 32 web/API tests. This report supersedes the earlier local reconstruction metrics; the shared original cosine TextRank core now produces 16/30 required items at three sentences and 24/30 at five.
