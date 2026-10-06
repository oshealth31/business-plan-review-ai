"""Turns an assessment result into what an applicant should see.

Applicant-facing language rules:
  * "readiness against a generic template" - never a prediction of any funder's decision.
  * No weights and no percentage score (false precision, and it invites gaming): counts and a band instead.
  * "mentioned" is a keyword match, not proof - the report says "make sure it is backed up".
  * Every gap carries a way to fix it and the question a reviewer is likely to ask.
"""
from __future__ import annotations

from typing import Any, Optional

from . import analysis as A
from . import templates as T

DISCLAIMER = ('This is a readiness check against a checklist, produced by software. It is not advice, not a '
              'prediction of any funder\'s decision, and not endorsed by any funder. Keyword checks cannot judge the quality '
              'of your evidence. Always read the funder\'s own application guidelines.')

STATE_LABELS = {
    'met': 'Meets the bar', 'not_met': 'Does not meet the bar', 'mentioned': 'Mentioned - back it up',
    'missing': 'Not found in your plan', 'cannot_assess': 'Could not check', 'judgement': 'For the reviewer to judge',
}
_ORDER = {'not_met': 0, 'missing': 1, 'cannot_assess': 2, 'mentioned': 3, 'judgement': 4, 'met': 5}
BANDS = {
    'needs_work': 'Needs work before you submit',
    'mostly_covered': 'Mostly covered - a few gaps to close',
    'well_covered': 'Well covered against this template',
    'incomplete': 'We could not finish checking - add or confirm your figures',
}
FIGURE_LABELS = [('revenue', 'Annual revenue'), ('expenses', 'Annual expenses'), ('profit', 'Profit'),
                 ('margin', 'Operating margin'), ('funding', 'Funding requested'), ('contribution', 'Your contribution'),
                 ('owner_contribution_pct', 'Your share of total project cost')]
ORIGIN_LABELS = {'document': 'Read from your plan - please confirm', 'officer_override': 'Confirmed by you',
                 'application_form': 'From the details you entered'}


def criterion_state(c: dict) -> str:
    s, kind = c['status'], c['kind']
    if kind == 'qualitative':
        return 'judgement'
    if s == 'pass':
        return 'met'
    if s == 'fail':
        return 'not_met'
    if s == 'unknown':
        return 'cannot_assess'
    if s == 'mentioned':
        return 'mentioned'
    if s == 'negated':
        return 'not_met'
    return 'missing'  # not_mentioned


def _counts(states: list[tuple[str, bool]]) -> dict[str, int]:
    covered = sum(1 for s, _ in states if s in ('met', 'mentioned'))
    gaps = sum(1 for s, _ in states if s in ('not_met', 'missing'))
    return {'covered': covered, 'gaps': gaps, 'to_confirm': sum(1 for s, _ in states if s == 'cannot_assess'),
            'judgement': sum(1 for s, _ in states if s == 'judgement'), 'total': len(states)}


def readiness_band(states: list[tuple[str, bool]]) -> dict[str, Any]:
    """states = [(state, required)]. Returns band id, label and the numbers behind it."""
    counts = _counts(states)
    required_gaps = sum(1 for s, req in states if req and s in ('not_met', 'missing'))
    required_open = sum(1 for s, req in states if req and s == 'cannot_assess')
    assessable = counts['covered'] + counts['gaps']
    if required_gaps:
        band = 'needs_work'
    elif required_open or assessable == 0:
        band = 'incomplete'
    elif counts['gaps'] == 0:
        band = 'well_covered'
    elif counts['covered'] / assessable >= 0.7:
        band = 'mostly_covered'
    else:
        band = 'needs_work'
    return {'band': band, 'label': BANDS[band], 'required_outstanding': required_gaps + required_open, **counts}


def quick_scan(result: dict) -> dict:
    """The free teaser: the band and the counts, with no criterion names, advice or flags."""
    states = [(criterion_state(c), bool(c['mandatory'])) for c in result['rubric']['criteria']]
    b = readiness_band(states)
    return {
        'band': b['band'], 'label': b['label'], 'required_outstanding': b['required_outstanding'],
        'counts': {k: b[k] for k in ('covered', 'gaps', 'to_confirm', 'judgement', 'total')},
        'figures_to_confirm': [k for k in result.get('needs_confirmation', []) if k in ('revenue', 'expenses')],
        'message': ('Unlock the full report to see which items are affected, why a reviewer would ask, and how to fix each one.'),
        'disclaimer': DISCLAIMER,
    }


def _applicant_detail(state: str, c: dict) -> str:
    if state in ('met', 'not_met') and c['kind'] == 'numeric':
        return c['detail']
    if state == 'mentioned':
        extra = (' Some sentences say this is missing or not done yet - make sure the plan does not contradict itself.'
                 if c.get('negated_mentions') else '')
        return ('We found wording about this in your plan. A keyword match is not proof - make sure the plan backs it up '
                'with numbers or an attached document.' + extra)
    if state == 'not_met':  # negated evidence
        return 'Your plan only mentions this as missing or not yet done.'
    if state == 'missing':
        return 'We did not find this in your plan.'
    if state == 'cannot_assess':
        return 'We could not check this because a figure is missing. Add it to your plan or confirm your figures.'
    return c.get('ai_note') or 'A reviewer will judge this.'


def applicant_report(result: dict, template: dict, check: Optional[dict] = None) -> dict:
    guide = T.criterion_guidance(template)
    items = []
    for c in result['rubric']['criteria']:
        st = criterion_state(c)
        g = guide.get(c['key'], {})
        items.append({
            'key': c['key'], 'label': c['label'], 'required': bool(c['mandatory']), 'state': st,
            'state_label': STATE_LABELS[st], 'detail': _applicant_detail(st, c),
            'requirement': g.get('requirement', ''), 'look_for': g.get('look_for', []),
            'reviewer_asks': g.get('asks', ''),
            'how_to_fix': g.get('advice', '') if st != 'met' else '',
            'ai_note': '' if st == 'judgement' else c.get('ai_note', ''),  # for judgement items the note is the detail
            'ai_quote': c.get('ai_quote', ''), 'ai_quote_verified': bool(c.get('ai_quote_verified')),
        })
    items.sort(key=lambda i: (_ORDER[i['state']], not i['required'], i['label']))
    band = readiness_band([(i['state'], i['required']) for i in items])

    sources = result.get('sources', {})
    figures = []
    for key, label in FIGURE_LABELS:
        v = result['metrics'].get(key)
        s = sources.get(key) or {}
        figures.append({'key': key, 'label': label, 'value': v, 'unit': '%' if key in ('margin', 'owner_contribution_pct') else 'money',
                        'origin': ORIGIN_LABELS.get(s.get('origin', ''), ''), 'source_line': s.get('line', ''),
                        'needs_confirmation': key in result.get('needs_confirmation', [])})

    flags = [{'severity': r['severity'], 'title': r['title'], 'detail': r.get('detail', ''), 'quote': r.get('quote', ''),
              'quote_verified': bool(r.get('quote_verified')), 'by': r.get('source', 'rule')}
             for r in result.get('risks', []) if not r.get('criterion')]
    flags.sort(key=lambda f: {'high': 0, 'medium': 1, 'low': 2}.get(f['severity'], 3))
    back_up = [{'claim': e['claim'], 'detail': e.get('detail', ''), 'status': e['status'], 'quote': e.get('quote', ''),
                'quote_verified': bool(e.get('quote_verified'))}
               for e in result.get('evidence', [])
               if e.get('source') == 'ai' and e['status'] in ('unsupported', 'missing', 'contradictory', 'needs_verification')]
    ai = result.get('ai', {})
    questions = [q['question'] for q in A.build_dd_questions(result)][:10]
    return {
        'template': {'id': template['id'], 'name': template['name'], 'version': template['version'],
                     'source_note': template['source_note'], 'basis': template['basis'],
                     'funder': template.get('funder'), 'retrieved': template.get('retrieved'),
                     'sources': list(template.get('sources', []))},
        'documents_to_prepare': list(template.get('attachments', [])),
        'confirm_yourself': list(template.get('self_checks', [])),
        'notes': list(template.get('notes', [])),
        'summary': band, 'items': items, 'figures': figures, 'flags': flags, 'claims_to_back_up': back_up,
        'reviewer_questions': questions,
        'overview': result.get('executive_summary', '') if ai.get('mode') == 'llm' else '',
        'strengths': result.get('strengths', []),
        'ai': {'mode': ai.get('mode', 'rules_only'), 'message': ai.get('message', '')},
        'disclaimer': DISCLAIMER,
    }
