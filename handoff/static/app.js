'use strict';
const $ = id => document.getElementById(id);
const state = {csrf: '', shift: null, draft: null, dirty: false, shifts: [], notes: [], shiftCursor: 0, noteCursor: 0};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = error ? 'error' : '';
  $('notice').hidden = false;
  if (error) $('notice').scrollIntoView({block: 'nearest'});
}
async function api(path, method = 'GET', data) {
  const headers = {'X-CSRF-Token': state.csrf};
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch('/api/v1' + path, {method, headers, credentials: 'same-origin', body: data === undefined ? undefined : JSON.stringify(data)});
  const value = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    if (response.status === 401) notice('Please sign in again. Your unsaved text is still on this page.', true);
    const fields = value.error?.fields || {};
    throw new Error([value.error?.message || 'The request failed.', ...Object.values(fields)].join(' '));
  }
  return value;
}
function on(id, event, action) {
  $(id).addEventListener(event, async e => {
    if (event === 'submit') e.preventDefault();
    const button = event === 'submit' ? e.target.querySelector('button[type="submit"]') : e.currentTarget;
    if (button?.tagName === 'BUTTON') button.disabled = true;
    try { await action(e); }
    catch (error) { notice(error.message, true); }
    finally {
      if (button?.tagName === 'BUTTON') button.disabled = false;
      updateApproval();
    }
  });
}
function date(iso) { return new Date(iso).toLocaleString([], {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}); }
function allowSwitch() {
  if (state.generating) { notice('Wait for summary generation to finish before switching.', true); return false; }
  if (!state.dirty) return true;
  notice('Save your review before switching drafts or shifts.', true);
  return false;
}
async function boot() {
  const session = await api('/session');
  state.csrf = session.csrf_token;
  $('login').hidden = session.authenticated;
  $('workspace').hidden = !session.authenticated;
  $('signout').hidden = !session.authenticated;
  $('account').textContent = session.user?.username || '';
  if (session.authenticated) await loadShifts(true);
}
async function loadShifts(reset = false) {
  if (reset) { state.shifts = []; state.shiftCursor = 0; }
  const page = await api('/shifts?limit=25&after_seq=' + state.shiftCursor);
  state.shifts.push(...page.items);
  state.shiftCursor = page.next_after_seq;
  $('more-shifts').hidden = page.items.length < 25;
  renderShifts();
}
function renderShifts() {
  $('shift-count').textContent = state.shifts.length;
  $('shift-list').replaceChildren();
  for (const shift of state.shifts) {
    const button = element('button', undefined, 'shift-button' + (state.shift?.id === shift.id ? ' selected' : ''));
    button.append(element('span', shift.label), element('small', 'Created ' + date(shift.created_at)));
    button.setAttribute('aria-pressed', String(state.shift?.id === shift.id));
    button.addEventListener('click', () => selectShift(shift).catch(e => notice(e.message, true)));
    $('shift-list').append(button);
  }
}
async function selectShift(shift) {
  if (!allowSwitch()) return;
  if ($('note-text').value.trim() && state.shift?.id !== shift.id) {
    notice('Save or clear your note before switching shifts.', true); return;
  }
  state.shift = shift; state.draft = null;
  $('shift-description').textContent = shift.label;
  $('note-form').hidden = false; $('draft-tools').hidden = false;
  renderShifts(); renderDraft();
  await loadNotes(true);
  await loadHistory();
}
async function loadNotes(reset = false) {
  const shiftId = state.shift.id;
  if (reset) { state.notes = []; state.noteCursor = 0; }
  const page = await api('/shifts/' + shiftId + '/notes?limit=25&after_seq=' + state.noteCursor);
  if (state.shift.id !== shiftId) return;
  state.notes.push(...page.items); state.noteCursor = page.next_after_seq;
  $('more-notes').hidden = page.items.length < 25;
  $('note-count').textContent = state.notes.length;
  $('note-list').replaceChildren();
  if (!state.notes.length) $('note-list').append(element('p', 'No notes yet. Add the first note below.', 'empty'));
  for (const note of state.notes) {
    const card = element('article', undefined, 'note-card');
    const label = element('div', undefined, 'note-label');
    label.append(element('span', 'NOTE ' + note.seq.toString().padStart(2, '0')), element('time', date(note.created_at)));
    card.append(label, element('p', note.text)); $('note-list').append(card);
  }
}
async function loadHistory() {
  const shiftId = state.shift.id;
  let cursor = 0, records = [], page;
  do {
    page = await api('/shifts/' + shiftId + '/summaries?limit=100&after_seq=' + cursor);
    records.push(...page.items); cursor = page.next_after_seq;
  } while (page.items.length === 100);
  if (state.shift.id !== shiftId) return;
  $('draft-history').replaceChildren(new Option('Choose a saved draft', ''));
  for (const draft of records.reverse()) {
    $('draft-history').append(new Option(`${draft.status === 'approved' ? 'Approved' : 'Draft'} · ${date(draft.created_at)} · v${draft.version}`, draft.id));
  }
  if (state.draft) $('draft-history').value = state.draft.id;
}
function markDirty() {
  state.dirty = true;
  $('save-state').textContent = 'Unsaved review changes';
  $('source-confirmed').checked = $('complete-confirmed').checked = false;
  updateApproval();
}
function renderDraft() {
  const draft = state.draft, approved = draft?.status === 'approved';
  $('draft-editor').hidden = !draft; $('draft-empty').hidden = !!draft;
  $('draft-status').textContent = draft ? draft.status.toUpperCase() : 'NO DRAFT';
  $('source-confirmed').checked = $('complete-confirmed').checked = false;
  $('review-items').replaceChildren();
  if (!draft) return;
  $('draft-meta').textContent = `Version ${draft.version} · ${draft.mode === 'textrank' ? 'TextRank suggestions' : 'Manual draft'} · ${draft.source_note_ids.length} source notes`;
  $('save-state').textContent = state.dirty ? 'Unsaved review changes' : 'All changes saved';
  for (const [index, item] of draft.items.entries()) {
    const card = element('article', undefined, 'review-item');
    const top = element('div', undefined, 'item-top');
    top.append(element('span', item.origin === 'extracted' ? 'EXTRACTED · ORIGINAL WORDING' : 'TECHNICIAN ADDITION', 'origin'));
    if (!approved) {
      const remove = element('button', 'Remove', 'quiet remove-item');
      remove.setAttribute('aria-label', 'Remove item ' + (index + 1));
      remove.addEventListener('click', () => { draft.items.splice(index, 1); markDirty(); renderDraft(); }); top.append(remove);
    }
    const text = element('textarea'); text.value = item.text; text.maxLength = 2000;
    text.readOnly = approved || item.origin === 'extracted';
    text.setAttribute('aria-label', 'Handoff item ' + (index + 1));
    text.addEventListener('input', () => { item.text = text.value; markDirty(); });
    const label = element('label', 'Category'); label.htmlFor = 'category-' + item.item_id;
    const select = element('select'); select.id = label.htmlFor; select.disabled = approved;
    for (const [value, caption] of [['unassigned', 'Choose category…'], ['unresolved', 'Unresolved issue'], ['completed', 'Completed troubleshooting'], ['pending', 'Pending action']]) select.append(new Option(caption, value));
    select.value = item.category; select.addEventListener('change', () => { item.category = select.value; markDirty(); });
    card.append(top, text, label, select);
    if (item.origin === 'extracted') {
      const actions = element('div', undefined, 'item-actions');
      const source = element('button', 'View source ↗', 'quiet');
      source.setAttribute('aria-label', 'View source for item ' + (index + 1));
      source.addEventListener('click', () => showSource(item.source_sentence_id).catch(e => notice(e.message, true)));
      actions.append(source);
      if (!approved) {
        const rewrite = element('button', 'Rewrite as technician', 'quiet');
        rewrite.addEventListener('click', () => { draft.items[index] = {...item, item_id: crypto.randomUUID(), origin: 'technician', source_sentence_id: null}; markDirty(); renderDraft(); }); actions.append(rewrite);
      }
      card.append(actions);
    }
    $('review-items').append(card);
  }
  for (const id of ['add-item', 'save-review', 'confirmations', 'approve']) $(id).hidden = approved;
  $('approval-details').hidden = !approved;
  if (approved) $('approval-details').textContent = `Approved ${date(draft.approval.approved_at)}. This handoff is saved and cannot be edited. New notes require a new handoff.`;
  updateApproval();
}
function updateApproval() {
  const draft = state.draft;
  $('approve').disabled = !draft || draft.status !== 'draft' || state.dirty || !draft.items.length || draft.items.some(i => i.category === 'unassigned') || !$('source-confirmed').checked || !$('complete-confirmed').checked;
}
async function showSource(sentenceId) {
  const source = state.draft.source_sentences.find(s => s.id === sentenceId);
  const note = await api('/notes/' + source.note_id);
  // API offsets count Unicode code points; JavaScript slice normally counts UTF-16 units.
  const characters = Array.from(note.text);
  $('source-title').textContent = 'Original source · Note ' + note.seq;
  $('source-content').replaceChildren(document.createTextNode(characters.slice(0, source.start).join('')), element('mark', characters.slice(source.start, source.end).join('')), document.createTextNode(characters.slice(source.end).join('')));
  $('source-dialog').showModal();
}
async function generate(mode) {
  if (!allowSwitch()) return;
  const data = {mode};
  if (mode === 'textrank') data.max_sentences = Number($('sentence-count').value);
  state.generating = true;
  $('generate').disabled = $('manual').disabled = true;
  $('draft-status').textContent = 'GENERATING…';
  let draft;
  try { draft = await api('/shifts/' + state.shift.id + '/summaries', 'POST', data); }
  finally {
    state.generating = false;
    $('generate').disabled = $('manual').disabled = false;
    $('draft-status').textContent = state.draft ? state.draft.status.toUpperCase() : 'NO DRAFT';
  }
  state.draft = draft; state.dirty = false; renderDraft(); await loadHistory();
  notice(mode === 'textrank' ? 'Draft ready. Review the source notes and assign a category to each item.' : 'Manual draft ready. Add the handoff items you want to include.');
}
on('login-form', 'submit', async () => {
  const session = await api('/session', 'POST', {username: $('username').value, password: $('password').value});
  state.csrf = session.csrf_token; $('password').value = ''; $('notice').hidden = true; await boot();
});
on('signout', 'click', async () => {
  if (!allowSwitch()) return;
  if ($('note-text').value.trim()) { notice('Save or clear your note before signing out.', true); return; }
  await api('/session', 'DELETE'); location.reload();
});
on('shift-form', 'submit', async () => {
  if (!allowSwitch()) return;
  if ($('note-text').value.trim()) { notice('Save or clear your note before creating a shift.', true); return; }
  const shift = await api('/shifts', 'POST', {label: $('shift-label').value});
  $('shift-label').value = ''; await loadShifts(true);
  if (!state.shifts.some(s => s.id === shift.id)) { state.shifts.push(shift); renderShifts(); }
  await selectShift(shift); notice('New shift created.');
});
on('note-form', 'submit', async () => {
  const submittedText = $('note-text').value;
  await api('/shifts/' + state.shift.id + '/notes', 'POST', {text: submittedText});
  if ($('note-text').value === submittedText) $('note-text').value = '';
  await loadNotes(true);
  notice(state.draft ? 'Note saved. Generate a fresh draft before approving a handoff.' : 'Original note saved.');
});
on('generate', 'click', () => generate('textrank'));
on('manual', 'click', () => generate('manual'));
on('draft-history', 'change', async () => {
  if (!allowSwitch()) { $('draft-history').value = state.draft?.id || ''; return; }
  const id = $('draft-history').value;
  state.draft = id ? await api('/summaries/' + id) : null; state.dirty = false; renderDraft();
});
on('add-item', 'click', () => {
  if (state.draft.items.length >= 30) throw new Error('A handoff can contain up to 30 items.');
  state.draft.items.push({item_id: crypto.randomUUID(), origin: 'technician', text: '', category: 'unassigned', source_sentence_id: null});
  markDirty(); renderDraft(); $('review-items').lastElementChild.querySelector('textarea').focus();
});
on('save-review', 'click', async () => {
  const draft = state.draft;
  state.draft = await api('/summaries/' + draft.id + '/review', 'PUT', {expected_version: draft.version, items: draft.items});
  state.dirty = false; renderDraft(); await loadHistory(); notice('Review saved. Check the confirmations when you are ready to approve.');
});
on('approve', 'click', async () => {
  const result = await api('/summaries/' + state.draft.id + '/approval', 'POST', {expected_version: state.draft.version, source_review_confirmed: $('source-confirmed').checked, completeness_confirmed: $('complete-confirmed').checked});
  state.draft = result.summary; renderDraft(); await loadHistory(); notice('Handoff approved and saved.');
});
on('source-confirmed', 'change', updateApproval);
on('complete-confirmed', 'change', updateApproval);
on('more-shifts', 'click', () => loadShifts());
on('more-notes', 'click', () => loadNotes());
$('close-source').addEventListener('click', () => $('source-dialog').close());
window.addEventListener('beforeunload', e => { if (state.dirty || $('note-text').value.trim()) { e.preventDefault(); e.returnValue = ''; } });
boot().catch(error => notice(error.message, true));
