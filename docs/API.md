# Alpha API contract

Base path `/api/v1`. JSON objects only for request bodies. Unknown JSON fields are rejected. IDs are canonical lowercase UUID strings; timestamps use UTC ISO 8601. Integer fields reject booleans. Responses include a request ID header; errors also include it in their JSON.

Obtain a session with `GET /session`, retain the cookie, and send its `csrf_token` as `X-CSRF-Token` on every mutation. Sign-in rotates both values. Sessions expire after 30 minutes of inactivity. After five failed attempts for a username/address pair in 15 minutes, further attempts return 429. This local throttle is not distributed infrastructure.

| Method and path | Request | Result |
| --- | --- | --- |
| GET `/session` | — | 200: authenticated, user or null, csrf_token |
| POST `/session` | username, password | 200: session status, rotated cookie |
| DELETE `/session` | CSRF header | 204: session removed, cookie cleared |
| GET `/shifts` | after_seq=0, limit=25 | 200: items, next_after_seq |
| POST `/shifts` | label | 201: shift |
| GET `/shifts/{id}/notes` | after_seq=0, limit=25 | 200: items, next_after_seq, shift_revision |
| POST `/shifts/{id}/notes` | text | 201: immutable note |
| GET `/notes/{id}` | — | 200: original note |
| POST `/shifts/{id}/summaries` | mode, optional max_sentences | 201: draft snapshot |
| GET `/shifts/{id}/summaries` | after_seq=0, limit=25 | 200: saved drafts/approvals; cursor is summary row sequence |
| GET `/summaries/{id}` | — | 200: summary |
| PUT `/summaries/{id}/review` | expected_version, items | 200: saved review |
| POST `/summaries/{id}/approval` | expected_version, source_review_confirmed, completeness_confirmed | 201: approval and summary |

Pagination accepts `after_seq >= 0` and `1 <= limit <= 100`. An empty page retains the cursor. Retrieval is ascending; the UI reverses history for display. Do not infer source scope from one displayed page: generation always loads all notes for the shift.

## Inputs and returned records

- Username: 3–64 letters, digits, underscore, dot, or hyphen. Password: 1–128 characters, not trimmed. Seeded account passwords are generated randomly on first setup.
- Shift label: 1–80 trimmed characters. Shift: id, team_id, label, seq, revision, created_at. New shift revision is 1.
- Note text: 1–5,000 code points after trimming outside whitespace. Note: id, shift_id, author_id, seq, text, created_at. Embedded whitespace and source text are preserved; the UI renders them as plain text. A correction is an additional note.
- Mode: `textrank` or `manual`. `max_sentences`: integer 1–10, defaults to 3 for TextRank; forbidden for manual. Total snapshot limits: 10,000 characters and 200 sentences, in both modes. An empty shift fails.
- Summary: id, shift_id, created_by, mode, status, version, source_revision, source_note_ids, source_sentences, items, created_at, algorithm_version, approval. First version is 1. Manual algorithm_version is null.
- Source sentence: id, note_id, start, end, text. Start/end are Python/Unicode code-point offsets in the stored note. Source text equals the original note slice exactly.
- Review item: item_id (UUID), origin (`extracted` or `technician`), text (1–2,000 characters), category (`unresolved`, `completed`, `pending`, or `unassigned`), source_sentence_id. Extracted identity/text/source cannot be changed. Technician additions use a new item_id and null source_sentence_id. Maximum 30 items; duplicates are rejected.
- Review save: expected_version must match the current draft. `items` replaces the complete final list. No-op saves retain the version. Changed reviews increment it and append an audit event. Both review save and approval reject a changed source revision.
- Approval: both confirmations must be literal true, all items categorized, and at least one item present. Approval increments the version and records id, summary_id, approved_by, approved_version, approved_at, source_revision. It makes the summary immutable. The same approval request/version is retry-safe.

## Errors

```json
{"error":{"code":"VERSION_CONFLICT","message":"This draft changed. Reload it before saving.","fields":{},"request_id":"server-generated-uuid"}}
```

400 INVALID_JSON; 415 UNSUPPORTED_MEDIA_TYPE; 401 UNAUTHENTICATED; 403 FORBIDDEN (CSRF); 404 NOT_FOUND (also other-team records); 405 METHOD_NOT_ALLOWED; 409 VERSION_CONFLICT / SOURCE_CHANGED / ALREADY_APPROVED; 413 PAYLOAD_TOO_LARGE (64 KiB); 422 VALIDATION_ERROR / NO_NOTES / INPUT_LIMIT_EXCEEDED / SENTENCE_TOO_LONG / REVIEW_INCOMPLETE; 429 RATE_LIMITED; 503 AI_UNAVAILABLE / AI_TIMEOUT / STORAGE_UNAVAILABLE; 500 INTERNAL_ERROR.

Extracted sentences longer than 2,000 characters require a manual draft rather than silent truncation. AI failure does not erase notes or create an approval. The interface keeps unsaved text when a request fails. Session expiry may require signing in again; preserve local unsaved text before reloading.
