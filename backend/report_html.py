"""Printable HTML version of an applicant report (standard library only; every value is escaped)."""
from __future__ import annotations

import html as _html

_STATE_CLASS = {'met': 'ok', 'mentioned': 'maybe', 'judgement': 'maybe', 'not_met': 'bad', 'missing': 'bad',
                'cannot_assess': 'maybe'}


def _e(x) -> str:
    return _html.escape('' if x is None else str(x))


def _money(v, currency: str) -> str:
    return 'not available' if v is None else f'{currency} {v:,.0f}'


def _figure(f: dict, currency: str) -> str:
    v = f['value']
    if v is None:
        return 'not available'
    return f'{v:.1f}%' if f['unit'] == '%' else _money(v, currency)


def render_report_html(title: str, report: dict, *, generated: str, version: str, currency: str = 'BWP') -> str:
    s = report['summary']
    rows = []
    for i in report['items']:
        extra = ''
        if i['how_to_fix']:
            extra += f"<div class='fix'><b>How to fix:</b> {_e(i['how_to_fix'])}</div>"
        if i['reviewer_asks']:
            extra += f"<div class='ask'><b>A reviewer may ask:</b> {_e(i['reviewer_asks'])}</div>"
        if i['ai_note']:
            extra += f"<div class='ai'><b>AI note:</b> {_e(i['ai_note'])}</div>"
        rows.append(
            f"<tr><td><b>{_e(i['label'])}</b>{' <span class=req>required</span>' if i['required'] else ''}"
            f"<div class=small>{_e(i['requirement'])}</div></td>"
            f"<td><span class='pill {_STATE_CLASS.get(i['state'], '')}'>{_e(i['state_label'])}</span></td>"
            f"<td>{_e(i['detail'])}{extra}</td></tr>")
    figures = ''.join(
        f"<tr><td>{_e(f['label'])}</td><td>{_e(_figure(f, currency))}</td>"
        f"<td>{_e(f['origin'])}{(' - <i>' + _e(f['source_line']) + '</i>') if f['source_line'] else ''}</td></tr>"
        for f in report['figures'])
    flags = ''.join(f"<li><b>{_e(f['severity'])}</b> - {_e(f['title'])}: {_e(f['detail'])}</li>" for f in report['flags']) \
        or '<li>Nothing further flagged.</li>'
    backup = ''.join(f"<li>{_e(c['claim'])}: {_e(c['detail'])}</li>" for c in report['claims_to_back_up'])
    questions = ''.join(f'<li>{_e(q)}</li>' for q in report['reviewer_questions']) or '<li>None.</li>'
    strengths = ''.join(f'<li>{_e(x)}</li>' for x in report['strengths'])
    t = report['template']
    def _lst(xs, f):
        return ''.join(f'<li>{f(x)}</li>' for x in xs)
    docs = (f"<h2>Documents to prepare</h2><p class='small'>Software cannot see your attachments, so these are not scored. "
            f"Check the funder's current list.</p><ul>{_lst(report.get('documents_to_prepare', []), lambda d: _e(d['item']) + ' <span class=small>(' + _e(d['when']) + ')</span>')}</ul>"
            if report.get('documents_to_prepare') else '')
    confirm = (f"<h2>Confirm these yourself</h2><ul>{_lst(report.get('confirm_yourself', []), lambda d: _e(d['text']) + ' <span class=small>(' + _e(d['source']) + ')</span>')}</ul>"
               if report.get('confirm_yourself') else '')
    notes = (f"<h2>Good to know</h2><ul>{_lst(report.get('notes', []), lambda d: _e(d['text']) + ' <span class=small>(' + _e(d['source']) + ')</span>')}</ul>"
             if report.get('notes') else '')
    srcs = (f"<h2>Sources (read {_e(t.get('retrieved'))})</h2><ul>{_lst(t.get('sources', []), lambda d: _e(d['title']) + ' - ' + _e(d['url']) + ' <span class=small>' + _e(d.get('note', '')) + '</span>')}</ul>"
            if t.get('sources') else '')
    overview = f"<h2>Overview</h2><p>{_e(report['overview'])}</p>" if report['overview'] else ''
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Readiness report - {_e(title)}</title>
<style>body{{font-family:Georgia,serif;color:#1c2b2a;margin:40px auto;max-width:900px;line-height:1.5;padding:0 18px}}
h1{{margin-bottom:2px}}h2{{border-bottom:1px solid #d9e2df;padding-bottom:5px;margin-top:30px}}
table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #d9e2df;padding:8px;text-align:left;vertical-align:top;font-size:14px}}
.small{{font-size:12px;color:#5b6b69}}.pill{{padding:2px 8px;border-radius:99px;font-size:12px;white-space:nowrap;border:1px solid #ccc}}
.ok{{background:#e3f4ea}}.maybe{{background:#fff3d6}}.bad{{background:#fde6e3}}.req{{font-size:11px;background:#eee;padding:1px 6px;border-radius:6px}}
.fix,.ask,.ai{{margin-top:6px;font-size:13px}}.box{{background:#f2f7f5;padding:14px;border-radius:8px}}.disc{{font-size:12px;color:#5b6b69;margin-top:30px}}</style></head><body>
<h1>Readiness report</h1><p class="small">{_e(title)} - {_e(report['template']['name'])} (template {_e(report['template']['version'])}) - generated {_e(generated)} - FundingLens Check v{_e(version)}</p>
<div class="box"><b>{_e(s['label'])}</b><br>Covered: {s['covered']} - Gaps: {s['gaps']} - Could not check: {s['to_confirm']} - For the reviewer to judge: {s['judgement']}
<br>Required items outstanding: {s['required_outstanding']}</div>
{overview}
<h2>Checklist</h2><table><tr><th>Item</th><th>Result</th><th>What we found and what to do</th></tr>{''.join(rows)}</table>
<h2>Figures we used</h2><table><tr><th>Figure</th><th>Value</th><th>Where it came from</th></tr>{figures}</table>
<h2>Other things a reviewer may question</h2><ul>{flags}</ul>
{('<h2>Claims to back up</h2><ul>' + backup + '</ul>') if backup else ''}
{('<h2>Strengths noticed</h2><ul>' + strengths + '</ul>') if strengths else ''}
<h2>Be ready to answer</h2><ul>{questions}</ul>
{docs}{confirm}{notes}{srcs}
<p class="disc">{_e(report['template']['source_note'])}<br>{_e(report['disclaimer'])}<br>{_e(report['ai']['message'])}</p></body></html>"""
