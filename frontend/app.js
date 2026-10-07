'use strict';
/* FundingLens Check - single-page client. No inline handlers; all text set via textContent (no innerHTML). */
/* DOM append/prepend/replaceChildren accept nested arrays and skip null/false, like h() does. */
for (const fn of ['append', 'prepend', 'replaceChildren']) {
  const orig = Element.prototype[fn];
  Element.prototype[fn] = function (...k) { return orig.apply(this, k.flat(Infinity).filter((x) => x != null && x !== false)); };
}
const $ = (s, r = document) => r.querySelector(s);
const state = { token: null, me: null, cfg: null, templates: [] };
try { state.token = sessionStorage.getItem('flc_token'); } catch (e) { /* storage blocked */ }

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const k of kids.flat(Infinity)) if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
const money = (v) => (v == null ? 'not available' : `${state.cfg ? state.cfg.currency : ''} ${Number(v).toLocaleString('en', { maximumFractionDigits: 0 })}`);
const fdate = (s) => (s ? new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '');
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('on'), 3500); }

async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  if (state.token) headers.Authorization = 'Bearer ' + state.token;
  let body = opts.body;
  if (body && !(body instanceof FormData) && !(body instanceof URLSearchParams) && typeof body !== 'string') { body = JSON.stringify(body); headers['Content-Type'] = 'application/json'; }
  const res = await fetch('/api' + path, { method: opts.method || 'GET', headers, body });
  if (res.status === 401 && state.token && !opts.noAuthRedirect) { signOut(); throw new Error('Your session has ended. Please sign in again.'); }
  if (opts.raw) return res;
  let data = null; try { data = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) { const e = new Error(detailText(data) || `Request failed (${res.status})`); e.status = res.status; e.data = data; throw e; }
  return data;
}
function detailText(d) { if (!d) return ''; if (typeof d.detail === 'string') return d.detail; if (Array.isArray(d.detail)) return d.detail.map((x) => x.msg).join(' '); return ''; }
function setToken(t) { state.token = t; try { t ? sessionStorage.setItem('flc_token', t) : sessionStorage.removeItem('flc_token'); } catch (e) { /* ignore */ } }
function signOut() { setToken(null); state.me = null; location.hash = '#/'; renderChrome(); route(); }
async function loadMe() { state.me = state.token ? await api('/me').catch(() => null) : null; if (!state.me) setToken(null); }

/* ---------- chrome ---------- */
const logo = () => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 32 32'); s.setAttribute('aria-hidden', 'true');
  s.innerHTML = '<rect width="32" height="32" rx="6" fill="#26384A"/><path d="M8 17l5 5 11-12" fill="none" stroke="#7DB7E8" stroke-width="3.5"/>'; return s; };
function renderChrome() {
  const top = $('#top'); top.replaceChildren();
  const nav = h('nav', { class: 'nav', 'aria-label': 'Main' });
  if (state.me) {
    nav.append(h('a', { href: '#/checks' }, 'My checks'), h('a', { href: '#/new' }, 'New check'), h('a', { href: '#/credits' }, 'Credits'), h('a', { href: '#/account' }, 'Account'));
    if (state.me.is_admin) nav.append(h('a', { href: '#/admin' }, 'Admin'));
    nav.append(h('span', { class: 'credit-chip', id: 'chip' }, `${state.me.credits} credits`), h('button', { type: 'button', onclick: signOut }, 'Sign out'));
  } else nav.append(h('a', { href: '#/signin' }, 'Sign in'));
  top.append(h('div', { class: 'in' }, h('a', { class: 'brand', href: state.me ? '#/checks' : '#/' }, logo(), 'FundingLens Check'), nav));
  const foot = $('#foot'); foot.replaceChildren(h('div', {}, `FundingLens Check v${state.cfg ? state.cfg.version : ''} - an independent readiness tool. Not a funder, not advice, and never a prediction of any funder's decision.`),
    state.cfg && state.cfg.support_email ? h('div', {}, 'Help: ', h('a', { href: 'mailto:' + state.cfg.support_email }, state.cfg.support_email)) : null);
  document.querySelectorAll('.nav a').forEach((a) => { if (a.getAttribute('href') === location.hash) a.setAttribute('aria-current', 'page'); });
   $('#foot').append(' ', h('a', { href: 'https://forms.gle/6qaZ6kgo8JC9EECYA', target: '_blank', rel: 'noopener noreferrer' }, 'Send feedback'));
}
function setChip(n) { if (state.me) state.me.credits = n; const c = $('#chip'); if (c) c.textContent = `${n} credits`; }

/* ---------- shared bits ---------- */
function strip(counts) {
  const tot = Math.max(1, counts.covered + counts.to_confirm + counts.gaps + counts.judgement);
  const seg = (cls, n) => h('i', { class: cls, style: `width:${(100 * n) / tot}%` });
  return h('div', {},
    h('div', { class: 'strip', role: 'img', 'aria-label': `${counts.covered} covered, ${counts.to_confirm} could not check, ${counts.gaps} gaps, ${counts.judgement} for the reviewer to judge` },
      seg('c', counts.covered), seg('t', counts.to_confirm), seg('g', counts.gaps), seg('j', counts.judgement)),
    h('div', { class: 'legend' },
      h('span', {}, h('span', { class: 'sw', style: 'background:var(--ok)' }), h('b', {}, counts.covered), ' covered'),
      h('span', {}, h('span', { class: 'sw', style: 'background:var(--bad)' }), h('b', {}, counts.gaps), ' gaps'),
      h('span', {}, h('span', { class: 'sw', style: 'background:#E3B33A' }), h('b', {}, counts.to_confirm), ' could not check'),
      h('span', {}, h('span', { class: 'sw', style: 'background:#9FB0BA' }), h('b', {}, counts.judgement), ' for the reviewer to judge')));
}
const errBox = (m) => h('div', { class: 'err', role: 'alert' }, m);
function showErr(host, e) { host.querySelectorAll('.err').forEach((x) => x.remove()); host.prepend(errBox(e.message || String(e))); host.scrollIntoView({ block: 'nearest' }); }
async function guarded(btn, host, fn) {
  btn.disabled = true;
  try { await fn(); } catch (e) { showErr(host, e); } finally { btn.disabled = false; }
}

/* ---------- landing + auth ---------- */
function viewLanding() {
  const m = $('#main'); m.replaceChildren(
    h('section', { class: 'hero' },
      h('div', {},
        h('h1', {}, 'Find the gaps in your business plan before the funder does.'),
        h('p', { class: 'lead' }, 'Upload your plan and see how well it covers what a funder asks for. Start with a free quick scan. Unlock the full report to see exactly what to add, and what a reviewer is likely to ask.'),
        h('p', {}, h('a', { class: 'btn', href: '#/signin' }, 'Check my plan'), ' ', h('a', { class: 'btn ghost', href: '#/templates' }, 'See what we check')),
        h('p', { class: 'small' }, 'We never predict whether a funder will approve you. We show what your plan covers and what it leaves out.')),
      h('div', { class: 'proof', 'aria-hidden': 'true' },
        h('div', {}, 'Our shop will sell ', h('span', { class: 'mk' }, 'strong demand'), ' for packaged mopane worms across Gaborone.'),
        h('div', { class: 'ln' }), h('div', { class: 'ln', style: 'width:82%' }),
        h('div', {}, 'Total project cost is ', h('span', { class: 'mk' }, 'P 480,000'), ', financed by our own contribution and the loan.'),
        h('div', { class: 'ln', style: 'width:90%' }), h('div', { class: 'ln', style: 'width:60%' }),
        h('span', { class: 'tag t1' }, 'Back this up'), h('span', { class: 'tag t2' }, 'No cash flow'), h('span', { class: 'tag t3' }, 'Costs covered'))),
    h('section', { class: 'how' },
      h('div', {}, h('h3', {}, 'Free quick scan'), h('p', {}, 'See how many items your plan covers and how many have gaps. No account balance needed.')),
      h('div', {}, h('h3', {}, 'Full report'), h('p', {}, `Every item, what we found, how to fix it, and the question a reviewer may ask. ${state.cfg ? state.cfg.pricing.full : 2} credits, then ${state.cfg ? state.cfg.pricing.recheck : 1} to re-check.`)),
      h('div', {}, h('h3', {}, 'Your plan stays yours'), h('p', {}, `Plans are deleted after ${state.cfg ? state.cfg.retention_days : 30} days, or sooner when you delete them. AI notes are optional and asked each time.`))));
}

function viewTemplates() {
  const m = $('#main'); m.replaceChildren(h('h1', {}, 'What we check'),
    h('p', {}, 'Each checklist is either a general one built from common lending practice, or one built from a funder\'s own published forms. Published ones show their sources and the date we read them.'));
  state.templates.forEach((t) => m.append(templateCard(t, false)));
  m.append(h('p', {}, h('a', { class: 'btn', href: '#/signin' }, 'Check my plan')));
}
function templateCard(t, selectable, selected) {
  return h('div', { class: 'tpl' + (selected ? ' sel' : '') },
    h('div', { class: 'basis' }, t.basis === 'published' ? `From ${t.funder} published forms` : 'General checklist'),
    h('h3', {}, t.name), h('p', { class: 'small' }, t.description),
    h('details', {}, h('summary', {}, `${t.criteria.length} items we look for`), h('ul', { class: 'tight' }, t.criteria.map((c) => h('li', {}, c.label, c.required ? ' (required)' : '')))),
    t.basis === 'published' ? h('p', { class: 'small' }, t.source_note) : null);
}
const noticeBox = h('details', { class: 'notice-box' },
  h('summary', {}, 'Read the terms and privacy notice'),
  h('p', {}, 'FundingLens Check is a demo readiness tool. It is not a funder, does not give financial or legal advice, and does not predict any funder\'s decision.'),
  h('p', {}, 'What we collect: your email address, a protected (hashed) version of your password, the business plan files you upload, and the reports generated from them.'),
  h('p', {}, 'Why: to run the checklist, show you your results, and manage credits.'),
  h('p', {}, 'How long we keep it: uploaded plans are deleted after 30 days, or sooner if you delete them. This demo may also reset without notice, which removes all accounts and data.'),
  h('p', {}, 'Who sees it: The person running the demo can technically access them, and will only look at them to fix a problem or answer your question. We do not sell your data. AI notes are switched off in this demo.'),
  h('p', {}, 'Your choices: you can ask for your account and files to be deleted at any time by contacting fundinglens@gmail.com.'),
  h('p', {}, 'Please do not upload ID numbers, bank details, or anything you would not want a tester to see.')
);
function viewSignin(mode = 'in') {
  const m = $('#main'); const host = h('div', { class: 'sheet auth' });
  const tabs = h('div', { class: 'tabs', role: 'tablist' },
    h('button', { type: 'button', role: 'tab', 'aria-selected': String(mode === 'in'), onclick: () => viewSignin('in') }, 'Sign in'),
    h('button', { type: 'button', role: 'tab', 'aria-selected': String(mode === 'up'), onclick: () => viewSignin('up') }, 'Create account'));
  const email = h('input', { type: 'email', id: 'em', autocomplete: 'email', required: true });
  const pw = h('input', { type: 'password', id: 'pw', autocomplete: mode === 'in' ? 'current-password' : 'new-password', required: true });
  const code = h('input', { type: 'text', id: 'inv', autocomplete: 'off', placeholder: 'FL-XXXX-XXXX' });
  const terms = h('input', { type: 'checkbox', id: 'tm' });
  const form = h('form', { novalidate: true }, h('label', { for: 'em' }, 'Email'), email, h('label', { for: 'pw' }, 'Password'), pw,
    mode === 'up' ? [h('p', { class: 'help' }, 'At least 12 characters.'),
      state.cfg && state.cfg.require_invite ? [h('label', { for: 'inv' }, 'Invite code'), code, h('p', { class: 'help' }, 'Check is invite-only while we test it. Your invite may include starting credits.')] : null,
     mode === 'up' ? noticeBox : null, h('div', { class: 'check-row' }, terms, h('label', { for: 'tm' }, 'I have read and accept the terms and privacy notice. (version ' + (state.cfg ? state.cfg.terms_version : '') + ').'))] : null);
  const btn = h('button', { class: 'btn', type: 'submit' }, mode === 'in' ? 'Sign in' : 'Create account');
  form.append(h('p', {}, btn));
  form.addEventListener('submit', (ev) => { ev.preventDefault(); guarded(btn, host, async () => {
    let r;
    if (mode === 'in') {
r = await api('/token', { method: 'POST', body: new URLSearchParams({ username: email.value, password: pw.value }).toString(), headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, noAuthRedirect: true });    } else r = await api('/auth/signup', { method: 'POST', body: { email: email.value, password: pw.value, invite_code: code.value || null, accept_terms: terms.checked } });
    setToken(r.access_token); await loadMe(); renderChrome(); location.hash = '#/checks'; if (mode === 'up') toast('Account created.');
  }); });
  host.append(h('h2', {}, mode === 'in' ? 'Welcome back' : 'Create your account'), tabs, form);
  m.replaceChildren(host); email.focus();
}

/* ---------- checks ---------- */
async function viewChecks() {
  const m = $('#main'); m.replaceChildren(h('div', { class: 'row' }, h('h1', {}, 'My checks'), h('a', { class: 'btn', href: '#/new' }, 'New check')));
  const rows = await api('/checks');
  if (!rows.length) { m.append(h('div', { class: 'sheet' }, h('h2', {}, 'No checks yet'), h('p', {}, 'Pick a checklist, upload your plan and get a free quick scan in under a minute.'), h('a', { class: 'btn', href: '#/new' }, 'Start a check'))); return; }
  m.append(h('div', { class: 'cards' }, rows.map((c) => h('a', { class: 'card', href: '#/check/' + c.id },
    h('h3', {}, c.title), h('div', { class: 'small' }, c.template_name),
    h('p', { class: 'small' }, c.has_document ? (c.band_label || 'Scanned') : 'No plan uploaded yet'),
    h('div', { class: 'small' }, `${c.full_runs} full report${c.full_runs === 1 ? '' : 's'} - deleted ${fdate(c.expires_at)}`)))));
}

function viewNew() {
  const m = $('#main'); const host = h('div', { class: 'sheet' });
  let sel = state.templates[0] ? state.templates[0].id : '';
  const list = h('div', {}); const draw = () => { list.replaceChildren(...state.templates.map((t) => {
    const r = h('input', { type: 'radio', name: 'tpl', id: 'tpl-' + t.id, value: t.id, checked: t.id === sel, onchange: () => { sel = t.id; draw(); } });
    return h('div', { class: 'tpl' + (t.id === sel ? ' sel' : '') }, h('div', { class: 'check-row', style: 'margin:0' }, r, h('label', { for: 'tpl-' + t.id }, h('span', { class: 'basis' }, t.basis === 'published' ? `From ${t.funder} published forms` : 'General checklist'), h('br'), h('b', {}, t.name))),
      h('p', { class: 'small', style: 'margin:6px 0 0 28px' }, t.best_for || t.description)); })); };
  draw();
  const title = h('input', { type: 'text', id: 'ti', maxlength: 200, required: true, placeholder: 'e.g. Mopane packaging plant' });
  const fund = h('input', { type: 'number', id: 'fu', min: 0, step: 'any', required: true });
  const own = h('input', { type: 'number', id: 'ow', min: 0, step: 'any', required: true });
  const btn = h('button', { class: 'btn', type: 'submit' }, 'Create check');
  const form = h('form', { novalidate: true }, h('label', { for: 'ti' }, 'Name this check'), title, h('label', {}, 'Which checklist?'), list,
    h('div', { class: 'grid2' }, h('div', {}, h('label', { for: 'fu' }, `Amount you are asking for (${state.cfg.currency})`), fund), h('div', {}, h('label', { for: 'ow' }, `Your own contribution (${state.cfg.currency})`), own)),
    h('p', { class: 'help' }, 'We use these two figures to test the funding-to-contribution split. You can correct revenue and expenses later.'), h('p', {}, btn));
  form.addEventListener('submit', (ev) => { ev.preventDefault(); guarded(btn, host, async () => {
    const c = await api('/checks', { method: 'POST', body: { title: title.value, template_id: sel, funding_request: Number(fund.value), owner_contribution: Number(own.value) } });
    location.hash = '#/check/' + c.id; }); });
  host.append(h('h1', {}, 'New check'), form); m.replaceChildren(host);
}

async function viewCheck(id) {
  const m = $('#main'); const d = await api('/checks/' + id);
  setChip(d.balance);
  const page = h('div', {});
  const top = h('div', { class: 'row' }, h('div', {}, h('h1', {}, d.title), h('p', { class: 'small' }, `${d.template.name} - requested ${money(d.funding_request)}, your contribution ${money(d.owner_contribution)}`)),
    h('button', { class: 'btn danger ghost sm', type: 'button', onclick: async () => { if (!confirm('Delete this check and its uploaded plan?')) return; await api('/checks/' + id, { method: 'DELETE' }); toast('Deleted.'); location.hash = '#/checks'; } }, 'Delete check'));
  page.append(top);
  const refresh = () => viewCheck(id);

  /* step 1: upload */
  const up = h('div', { class: 'sheet' }); const file = h('input', { type: 'file', id: 'fl', accept: '.pdf,.docx,.txt,.md,.csv' });
  const upBtn = h('button', { class: 'btn', type: 'submit' }, d.document ? 'Replace and rescan' : 'Upload and scan');
  const upForm = h('form', {}, h('label', { for: 'fl' }, 'Business plan (PDF, DOCX or TXT, up to ' + Math.round(state.cfg.max_upload_bytes / 1e6) + ' MB)'), file, h('p', {}, upBtn));
  upForm.addEventListener('submit', (ev) => { ev.preventDefault(); if (!file.files[0]) { showErr(up, new Error('Choose a file first.')); return; }
    guarded(upBtn, up, async () => { const fd = new FormData(); fd.append('file', file.files[0]); await api(`/checks/${id}/document`, { method: 'POST', body: fd }); toast('Scan complete.'); await refresh(); }); });
  up.append(h('h2', {}, 'Your plan'), d.document ? h('p', { class: 'small' }, `Uploaded: ${d.document.name}. Stored until ${fdate(d.expires_at)}, then deleted.`) : null, upForm,
    h('p', { class: 'small' }, 'Scanned PDFs without selectable text cannot be read. Export a text-based PDF or DOCX.'));
  page.append(up);

  /* step 2: quick scan */
  if (d.quick) {
    const q = d.quick; const box = h('div', { class: 'sheet' });
    box.append(h('h2', {}, 'Quick scan (free)'), h('p', { class: 'band ' + q.band }, q.label), strip(q.counts),
      q.required_outstanding ? h('p', {}, `${q.required_outstanding} required item${q.required_outstanding === 1 ? ' is' : 's are'} not yet covered.`) : null);
    if (q.figures_to_confirm.length) {
      const rev = h('input', { type: 'number', id: 'rv', min: 0, step: 'any', value: d.overrides && d.overrides.revenue != null ? d.overrides.revenue : '' });
      const exp = h('input', { type: 'number', id: 'ex', min: 0, step: 'any', value: d.overrides && d.overrides.expenses != null ? d.overrides.expenses : '' });
      const fb = h('button', { class: 'btn ghost sm', type: 'submit' }, 'Update scan');
      const ff = h('form', {}, h('div', { class: 'note' }, 'We could not confidently read your yearly revenue or expenses. Enter them to improve the scan (free).'),
        h('div', { class: 'grid2' }, h('div', {}, h('label', { for: 'rv' }, `Yearly revenue (${state.cfg.currency})`), rev), h('div', {}, h('label', { for: 'ex' }, `Yearly expenses (${state.cfg.currency})`), exp)), h('p', {}, fb));
      ff.addEventListener('submit', (ev) => { ev.preventDefault(); guarded(fb, box, async () => { await api(`/checks/${id}/figures`, { method: 'POST', body: { revenue: rev.value === '' ? null : Number(rev.value), expenses: exp.value === '' ? null : Number(exp.value) } }); toast('Scan updated.'); await refresh(); }); });
      box.append(ff);
    }
    page.append(box);

    /* step 3: unlock */
    const un = h('div', { class: 'sheet' }); const ai = h('input', { type: 'checkbox', id: 'ai' });
    const key = (self.crypto && crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).replace(/[^a-zA-Z0-9-]/g, '');
    const ub = h('button', { class: 'btn', type: 'button' }, d.full ? `Run a new full report (${d.price} credit${d.price === 1 ? '' : 's'})` : `Unlock full report (${d.price} credits)`);
    ub.addEventListener('click', () => guarded(ub, un, async () => {
      const r = await api(`/checks/${id}/full`, { method: 'POST', body: { use_ai: ai.checked }, headers: { 'Idempotency-Key': key } });
      setChip(r.balance); toast(r.billing_note || `Report ready. ${r.charged} credit(s) used.`); await refresh(); }).catch((e) => { if (e.status === 402) showErr(un, new Error(e.message + ' Add credits on the Credits page.')); else showErr(un, e); }));
    un.append(h('h2', {}, d.full ? 'Run another full report' : 'Unlock the full report'),
      h('p', {}, d.full ? `Fixed something? Re-checking costs ${state.cfg.pricing.recheck} credit within ${state.cfg.pricing.window_days} days of your last report.` : 'See each item, what we found, how to fix it and what a reviewer may ask. If the report cannot be produced you are not charged.'),
      d.ai_available ? h('div', { class: 'check-row' }, ai, h('label', { for: 'ai' }, 'Also add AI notes. This sends a copy of your plan text, with emails, phone numbers and ID numbers removed, to our AI provider for this report only.')) : h('p', { class: 'small' }, 'AI notes are not enabled on this service. The report uses the checklist rules.'),
      h('p', {}, ub, h('span', { class: 'small' }, `  You have ${d.balance} credit${d.balance === 1 ? '' : 's'}. `), d.balance < d.price ? h('a', { href: '#/credits' }, 'Add credits') : null));
    page.append(un);
  }
  if (d.full) page.append(reportView(d, id));
  m.replaceChildren(page);
}

function reportView(d, id) {
  const r = d.full.report; const s = r.summary; const box = h('div', { class: 'sheet', id: 'report' });
  const open = h('button', { class: 'btn ghost sm no-print', type: 'button' }, 'Open printable report');
  open.addEventListener('click', () => guarded(open, box, async () => {
    const res = await api(`/checks/${id}/report?run=${d.full.run.number}`, { raw: true }); if (!res.ok) throw new Error('Could not open the report.');
    const url = URL.createObjectURL(await res.blob()); window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000); }));
  box.append(h('div', { class: 'row' }, h('h2', {}, `Full report ${fdate(d.full.run.created_at)}`), open),
    d.full.stale ? h('div', { class: 'note' }, 'You changed this check after this report. Run a new full report to update it.') : null,
    h('p', { class: 'band ' + s.band }, s.label), strip({ covered: s.covered, gaps: s.gaps, to_confirm: s.to_confirm, judgement: s.judgement }),
    h('p', { class: 'small' }, `${s.required_outstanding} required item(s) outstanding. Checklist: ${r.template.name} (version ${r.template.version}).`),
    r.overview ? [h('h3', {}, 'Overview'), h('p', {}, r.overview)] : null,
    h('h3', {}, 'Checklist'),
    h('ul', { class: 'items' }, r.items.map((i) => h('li', { class: 'item ' + i.state },
      h('div', { class: 'rail' }),
      h('div', { class: 'body' }, h('h3', {}, i.label, h('span', { class: 'pill ' + i.state }, i.state_label), i.required ? h('span', { class: 'pill req' }, 'required') : null),
        h('div', { class: 'small' }, i.requirement), h('p', { style: 'margin:8px 0 0' }, i.detail),
        i.how_to_fix ? h('div', { class: 'margin' }, h('b', {}, 'How to fix: '), i.how_to_fix) : null,
        i.reviewer_asks ? h('div', { class: 'margin ask' }, h('b', {}, 'A reviewer may ask: '), i.reviewer_asks) : null,
        i.ai_note ? h('div', { class: 'margin ai' }, h('b', {}, 'AI note: '), i.ai_note) : null)))));
  if (r.figures.length) box.append(h('h3', {}, 'Figures we used'), h('div', { class: 'tablewrap' }, h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Figure'), h('th', {}, 'Value'), h('th', {}, 'Where it came from'))),
    h('tbody', {}, r.figures.map((f) => h('tr', {}, h('td', {}, f.label), h('td', {}, f.value == null ? 'not available' : f.unit === '%' ? f.value.toFixed(1) + '%' : money(f.value)), h('td', {}, f.origin, f.source_line ? ' - "' + f.source_line + '"' : '')))))));
  const list = (title, arr, fn) => (arr && arr.length ? [h('h3', {}, title), h('ul', { class: 'tight' }, arr.map((x) => h('li', {}, fn(x))))] : null);
  box.append(list('Other things a reviewer may question', r.flags, (f) => [h('b', {}, f.title), ': ', f.detail]),
    list('Claims to back up', r.claims_to_back_up, (c) => [h('b', {}, c.claim), c.detail ? ': ' + c.detail : '']),
    list('Strengths noticed', r.strengths, (x) => x),
    list('Be ready to answer', r.reviewer_questions, (x) => x),
    list('Documents to prepare', r.documents_to_prepare, (x) => [x.item, h('span', { class: 'small' }, ` (${x.when})`)]),
    r.documents_to_prepare && r.documents_to_prepare.length ? h('p', { class: 'small' }, 'We cannot see your attachments, so these are a reminder and are not scored. Check the funder\'s current list.') : null,
    list('Confirm these yourself', r.confirm_yourself, (x) => [x.text, h('span', { class: 'small' }, ` (${x.source})`)]),
    list('Good to know', r.notes, (x) => [x.text, h('span', { class: 'small' }, ` (${x.source})`)]),
    r.template.sources && r.template.sources.length ? [h('h3', {}, `Sources (read ${r.template.retrieved})`), h('ul', { class: 'tight' }, r.template.sources.map((x) => h('li', {}, h('a', { href: x.url, target: '_blank', rel: 'noopener noreferrer' }, x.title), h('span', { class: 'small' }, x.note ? ' - ' + x.note : ''))))] : null,
    h('p', { class: 'disc' }, r.template.source_note, h('br'), r.disclaimer, h('br'), r.ai.message));
  return box;
}

/* ---------- credits / account ---------- */
async function viewCredits() {
  const m = $('#main'); const c = await api('/credits'); setChip(c.balance);
  m.replaceChildren(h('h1', {}, 'Credits'), h('div', { class: 'sheet' }, h('p', { class: 'band' }, `${c.balance} credits`),
    h('p', {}, `A first full report costs ${state.cfg.pricing.full} credits. Re-checking the same plan within ${state.cfg.pricing.window_days} days costs ${state.cfg.pricing.recheck}. Quick scans are free.`),
    c.packs.length ? h('div', { class: 'cards' }, c.packs.map((p) => h('div', { class: 'card' }, h('h3', {}, p.name), h('p', {}, `${p.credits} credits - ${p.currency} ${p.price}`),
      p.url ? h('a', { class: 'btn sm', href: p.url, target: '_blank', rel: 'noopener noreferrer' }, 'Buy') : h('span', { class: 'small' }, 'Not available yet')))) : h('div', { class: 'note' }, 'Credit packs are not on sale yet. Ask for an invite or a top-up' + (state.cfg.support_email ? ' at ' + state.cfg.support_email : '') + '.'),
    h('p', { class: 'small' }, 'After you pay, credits are added to this email address, usually within a few minutes.')),
    h('div', { class: 'sheet' }, h('h2', {}, 'History'), c.entries.length ? h('div', { class: 'tablewrap' }, h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Date'), h('th', {}, 'Change'), h('th', {}, 'What for'))),
      h('tbody', {}, c.entries.map((e) => h('tr', {}, h('td', {}, fdate(e.created_at)), h('td', {}, (e.delta > 0 ? '+' : '') + e.delta), h('td', {}, labelReason(e.reason) + (e.note ? ' - ' + e.note : ''))))))) : h('p', {}, 'Nothing yet.')));
}
const labelReason = (r) => ({ grant_invite: 'Invite credits', grant_signup: 'Welcome credits', charge_full: 'Full report', charge_recheck: 'Re-check', purchase: 'Purchase', admin_grant: 'Credits added by support', admin_adjust: 'Adjustment' }[r] || r);

function viewAccount() {
  const m = $('#main'); const pwHost = h('div', { class: 'sheet' }); const delHost = h('div', { class: 'sheet' });
  const cur = h('input', { type: 'password', id: 'cp', autocomplete: 'current-password' }); const nw = h('input', { type: 'password', id: 'np', autocomplete: 'new-password' });
  const pb = h('button', { class: 'btn', type: 'submit' }, 'Change password');
  const pf = h('form', {}, h('label', { for: 'cp' }, 'Current password'), cur, h('label', { for: 'np' }, 'New password (12+ characters)'), nw, h('p', {}, pb));
  pf.addEventListener('submit', (ev) => { ev.preventDefault(); guarded(pb, pwHost, async () => { const r = await api('/me/password', { method: 'POST', body: { current_password: cur.value, new_password: nw.value } }); setToken(r.access_token); cur.value = nw.value = ''; toast('Password changed.'); }); });
  const dp = h('input', { type: 'password', id: 'dp', autocomplete: 'current-password' }); const db = h('button', { class: 'btn danger', type: 'submit' }, 'Delete my account');
  const df = h('form', {}, h('p', {}, 'This permanently deletes your plans, reports and personal details, and any unused credits. Payment records are kept without your name.'), h('label', { for: 'dp' }, 'Confirm with your password'), dp, h('p', {}, db));
  df.addEventListener('submit', (ev) => { ev.preventDefault(); if (!confirm('Delete your account permanently?')) return; guarded(db, delHost, async () => { await api('/me/delete', { method: 'POST', body: { password: dp.value } }); setToken(null); state.me = null; renderChrome(); location.hash = '#/'; toast('Your account was deleted.'); }); });
  pwHost.append(h('h2', {}, 'Password'), pf); delHost.append(h('h2', {}, 'Delete account'), df);
  m.replaceChildren(h('h1', {}, 'Account'), h('p', {}, state.me.email), pwHost, delHost);
}

/* ---------- admin ---------- */
async function viewAdmin() {
  const m = $('#main'); m.replaceChildren(h('h1', {}, 'Admin'));
  const [inv, users, pay, usage] = await Promise.all([api('/admin/invites'), api('/admin/users'), api('/admin/payments'), api('/admin/usage')]);
  const ib = h('div', { class: 'sheet' }); const cr = h('input', { type: 'number', id: 'ic', value: 5, min: 0 }); const em = h('input', { type: 'email', id: 'ie', placeholder: 'optional: lock to one email' });
  const mk = h('button', { class: 'btn', type: 'submit' }, 'Create invite');
  const f = h('form', {}, h('div', { class: 'grid2' }, h('div', {}, h('label', { for: 'ic' }, 'Credits included'), cr), h('div', {}, h('label', { for: 'ie' }, 'Email (optional)'), em)), h('p', {}, mk));
  f.addEventListener('submit', (ev) => { ev.preventDefault(); guarded(mk, ib, async () => { const r = await api('/admin/invites', { method: 'POST', body: { credits: Number(cr.value), email: em.value || null } }); toast('Invite ' + r.code); viewAdmin(); }); });
  ib.append(h('h2', {}, 'Invites'), f, h('div', { class: 'tablewrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Code', 'Credits', 'Used', 'Status', ''].map((x) => h('th', {}, x)))),
    h('tbody', {}, inv.map((i) => h('tr', {}, h('td', {}, i.code), h('td', {}, i.credits), h('td', {}, `${i.uses}/${i.max_uses}`), h('td', {}, i.active ? 'active' : 'revoked'),
      h('td', {}, i.active ? h('button', { class: 'btn ghost sm', type: 'button', onclick: async () => { await api(`/admin/invites/${i.id}/revoke`, { method: 'POST' }); viewAdmin(); } }, 'Revoke') : '')))))));
  const gb = h('div', { class: 'sheet' }); const ge = h('input', { type: 'email', id: 'ge', required: true }); const gc = h('input', { type: 'number', id: 'gc', value: 5 }); const gr = h('input', { type: 'text', id: 'gr', value: 'Manual top-up', minlength: 3 });
  const gbtn = h('button', { class: 'btn', type: 'submit' }, 'Apply'); const gf = h('form', {}, h('div', { class: 'grid2' }, h('div', {}, h('label', { for: 'ge' }, 'User email'), ge), h('div', {}, h('label', { for: 'gc' }, 'Credits (negative to remove)'), gc)), h('label', { for: 'gr' }, 'Reason'), gr, h('p', {}, gbtn));
  gf.addEventListener('submit', (ev) => { ev.preventDefault(); guarded(gbtn, gb, async () => { const r = await api('/admin/credits', { method: 'POST', body: { email: ge.value, credits: Number(gc.value), reason: gr.value } }); toast(`${r.email} now has ${r.balance}.`); viewAdmin(); }); });
  gb.append(h('h2', {}, 'Adjust credits'), gf);
  const pb = h('div', { class: 'sheet' }, h('h2', {}, 'Payments'), pay.length ? h('div', { class: 'tablewrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Event', 'Email', 'Credits', 'Status'].map((x) => h('th', {}, x)))),
    h('tbody', {}, pay.map((p) => h('tr', {}, h('td', {}, p.event_id), h('td', {}, p.email), h('td', {}, p.credits), h('td', {}, p.status)))))) : h('p', {}, 'No payments yet.'));
  const ub = h('div', { class: 'sheet' }, h('h2', {}, 'Users'), h('p', { class: 'small' }, `${users.length} user(s).`), h('details', {}, h('summary', {}, 'Usage summary'), h('pre', { style: 'overflow:auto;font-size:.85rem' }, JSON.stringify(usage, null, 2))));
  m.append(ib, gb, pb, ub);
}

/* ---------- router ---------- */
const AUTHED = /^#\/(checks|new|check\/|credits|account|admin)/;
async function route() {
  const hash = location.hash || '#/'; const m = $('#main');
  try {
    if (AUTHED.test(hash) && !state.me) { location.hash = '#/signin'; return; }
    if (hash === '#/' || hash === '') state.me ? (location.hash = '#/checks') : viewLanding();
    else if (hash === '#/signin') state.me ? (location.hash = '#/checks') : viewSignin('in');
    else if (hash === '#/templates') viewTemplates();
    else if (hash === '#/checks') await viewChecks();
    else if (hash === '#/new') viewNew();
    else if (hash.startsWith('#/check/')) await viewCheck(hash.slice(8));
    else if (hash === '#/credits') await viewCredits();
    else if (hash === '#/account') viewAccount();
    else if (hash === '#/admin' && state.me.is_admin) await viewAdmin();
    else viewLanding();
  } catch (e) { m.replaceChildren(errBox(e.message), h('p', {}, h('a', { href: '#/' }, 'Back to start'))); }
  document.title = 'FundingLens Check';
  document.querySelectorAll('.nav a').forEach((a) => (a.getAttribute('href') === hash ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  m.focus({ preventScroll: true }); window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
(async function init() {
  try { [state.cfg, state.templates] = await Promise.all([api('/config'), api('/templates')]); } catch (e) { $('#main').append(errBox('The service is not reachable right now. Please try again shortly.')); return; }
  await loadMe(); renderChrome(); route();
})();
