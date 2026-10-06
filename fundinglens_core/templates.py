"""Generic assessment templates for FundingLens Check.

These are NOT any funder's real criteria. They are generic checklists compiled from common
lending and grant-readiness practice, so an applicant can see whether a plan covers the things
reviewers commonly look for. Each template says so (`source_note`) and the UI repeats it.

When a funder shares or licenses its own checklist, add it here as another template with
`basis='funder'` and a `funder` name - the engine does not change.

Pure Python: no web framework or database.
"""
from __future__ import annotations

import copy
from typing import Any, Optional

TEMPLATES_VERSION = '2026.1'

SOURCE_NOTE_GENERIC = ('Generic template compiled from common lending and grant-readiness practice. '
                       'It is not the criteria of any specific funder and does not predict any funder\'s decision.')

# --------------------------------------------------------------------------------------
# Criterion library. Each entry is a complete analysis criterion plus applicant guidance:
#   advice  - how to fix a gap        asks - the question a reviewer will probably ask
# --------------------------------------------------------------------------------------
_LIB: dict[str, dict[str, Any]] = {
    'operating_margin': dict(
        label='Operating margin', kind='numeric', metric='margin', comparator='>=',
        description='Annual operating margin (profit / revenue) should meet the minimum.',
        advice='Show a clear path from revenue to profit: your prices, unit costs and expected volumes. If the margin is thin, '
               'explain what improves it (pricing, cost savings, volume ramp-up) and add a "what if sales are 20% lower" case.',
        asks='How sensitive is your profit to lower sales or higher costs?'),
    'funding_to_contribution': dict(
        label='Funding compared with your own contribution', kind='numeric', metric='funding_to_contribution', comparator='<=',
        description='The amount requested should not be a very large multiple of what you put in yourself.',
        advice='Increase your own contribution (cash, equipment or stock, with values), reduce the amount requested, or add '
               'another funding source - and state it clearly in the plan.',
        asks='How much of your own money and assets is at risk in this project?'),
    'owner_contribution_pct': dict(
        label='Your contribution as a share of total project cost', kind='numeric', metric='owner_contribution_pct', comparator='>=',
        description='Your own contribution divided by (funding requested + your contribution).',
        advice='State your contribution in money terms and list what it consists of (cash, equipment, stock). Contributions in '
               'kind should have a supported value, for example a quotation or valuation.',
        asks='What are you contributing yourself, and how is it valued?'),
    'market_demand': dict(
        label='Market and demand', kind='evidence',
        keywords=['market', 'demand', 'target customers', 'market size', 'customer base'],
        description='The plan should describe who will buy, how many, and why.',
        advice='Name your target customers and the size of the opportunity. Back it with something checkable: a survey, '
               'letters of intent, orders, pre-sales or sales history. Avoid claims like "everyone needs this".',
        asks='Who exactly will buy this, how do you know, and how many?'),
    'competitor_analysis': dict(
        label='Competitors', kind='evidence',
        keywords=['competitor', 'competition', 'competitive', 'alternatives'],
        description='The plan should identify competitors and explain how you differ.',
        advice='List your three to five closest competitors (including informal ones) and say how your price, quality, location '
               'or service differs. A short table works well.',
        asks='Who else serves these customers today, and why would they choose you?'),
    'supplier_quotations': dict(
        label='Supplier quotations for major purchases', kind='evidence',
        keywords=['quotation', 'quote', 'supplier', 'invoice', 'price list'],
        description='Equipment and other large costs should be backed by supplier quotations.',
        advice='Attach current quotations (usually less than 30-90 days old) for each major item and make the totals in your '
               'budget match them. Say which supplier you will use.',
        asks='Where do your cost figures come from? Can I see the quotations?'),
    'cash_flow': dict(
        label='Cash-flow projection', kind='evidence',
        keywords=['cash flow', 'cashflow', 'working capital', 'monthly projection', 'cash projection'],
        description='A monthly cash-flow or working-capital projection should be included.',
        advice='Add a 12-month (ideally 24-month) monthly cash-flow table: money in, money out, closing balance. Show how you '
               'fund the gap between paying suppliers and being paid.',
        asks='Will you run out of cash in the first year, and how do you cover the gap?'),
    'management_experience': dict(
        label='Management and team experience', kind='evidence',
        keywords=['management experience', 'experience', 'qualifications', 'curriculum vitae', 'track record', 'years in'],
        description='The plan should show that the people running the business can do it.',
        advice='Add short bios with relevant years of experience and results (not only job titles). Say who is responsible for '
               'finance, operations and sales, and attach CVs.',
        asks='Why are you the right people to run this, and who covers the gaps in skills?'),
    'compliance': dict(
        label='Licences, registration and tax compliance', kind='evidence',
        keywords=['licence', 'license', 'registration', 'registered', 'tax clearance', 'compliance', 'permit'],
        description='Required licences, registrations and tax status should be mentioned.',
        advice='List the licences and permits your business needs, which you already hold (with numbers or dates) and which are '
               'pending. Attach registration and tax-clearance documents.',
        asks='Is the business legally registered and able to operate in this activity today?'),
    'business_viability': dict(
        label='Overall business model viability', kind='qualitative', weight=0.0,
        description='Is the business model coherent and credible given the evidence supplied? (reviewer judgement)',
        advice='Read your plan as a sceptical stranger: does each claim have a number or a document behind it?',
        asks='Does the whole story hang together?'),
}


def _c(key: str, *, threshold=None, mandatory=False, weight=1.0, keywords=None, label=None, description=None, advice=None):
    c = copy.deepcopy(_LIB[key]) if key in _LIB else {}
    c['key'] = key
    c['mandatory'] = mandatory
    if 'weight' not in c:
        c['weight'] = weight
    if threshold is not None:
        c['threshold'] = float(threshold)
    if keywords is not None:
        c['keywords'] = keywords
    if label:
        c['label'] = label
    if description:
        c['description'] = description
    if advice:
        c['advice'] = advice
    c.setdefault('keywords', [])
    c['enabled'] = True
    return c


def _extra(key: str, label: str, keywords: list[str], description: str, advice: str, asks: str, *,
           mandatory=False, weight=1.0):
    return dict(key=key, label=label, kind='evidence', keywords=keywords, description=description, advice=advice,
                asks=asks, mandatory=mandatory, weight=weight, enabled=True)


TEMPLATES: list[dict[str, Any]] = [
    dict(
        id='sme-growth-general', name='SME growth funding (general)', version=TEMPLATES_VERSION, basis='generic',
        description='A broad checklist for an established small business asking for growth funding (equipment, stock, expansion).',
        best_for='Trading and production businesses with at least some sales history.',
        source_note=SOURCE_NOTE_GENERIC,
        criteria=[
            _c('operating_margin', threshold=15, weight=2),
            _c('funding_to_contribution', threshold=5, weight=1),
            _c('owner_contribution_pct', threshold=10, mandatory=True, weight=2),
            _c('market_demand', mandatory=True, weight=2),
            _c('competitor_analysis'),
            _c('supplier_quotations'),
            _c('cash_flow', weight=2),
            _c('management_experience'),
            _c('compliance'),
            _c('business_viability'),
        ]),
    dict(
        id='agri-processing', name='Agri-processing and agribusiness', version=TEMPLATES_VERSION, basis='generic',
        description='For businesses that grow, aggregate or process agricultural products and sell to retailers or institutions.',
        best_for='Food processing, packaging, aggregation, poultry, horticulture and similar.',
        source_note=SOURCE_NOTE_GENERIC,
        criteria=[
            _c('operating_margin', threshold=12, weight=2),
            _c('funding_to_contribution', threshold=5, weight=1),
            _c('owner_contribution_pct', threshold=10, mandatory=True, weight=2),
            _c('market_demand', mandatory=True, weight=2),
            _extra('offtake_evidence', 'Buyers and off-take evidence',
                   ['off-take', 'offtake', 'purchase order', 'letter of intent', 'supply agreement', 'contract with', 'standing order'],
                   'Evidence that named buyers will actually purchase your output.',
                   'Attach signed orders, letters of intent or supply agreements from named buyers, with volumes, prices and '
                   'delivery terms. One real buyer is stronger than a long list of prospects.',
                   'Who has committed to buy, how much, and at what price?', mandatory=True, weight=2),
            _extra('raw_material_supply', 'Reliable supply of raw materials',
                   ['raw material', 'farmers', 'outgrower', 'out-grower', 'harvest', 'supply of produce', 'feedstock'],
                   'How you secure enough input of the right quality through the year, including seasonality.',
                   'Describe where inputs come from, who supplies them, the seasonal pattern, storage, and what happens in a poor '
                   'season (drought, disease, price spikes). Supplier agreements help.',
                   'What if the harvest is poor or input prices rise?'),
            _c('supplier_quotations'),
            _c('cash_flow', weight=2, advice='Add a monthly cash-flow that reflects seasonality: when you pay for inputs, when '
               'buyers pay you, and how the gap is financed. Agri businesses usually need more working capital than expected.'),
            _extra('food_safety_permits', 'Food safety, health and sector permits',
                   ['food safety', 'haccp', 'health permit', 'health certificate', 'veterinary', 'bureau of standards',
                    'certificate of compliance', 'licence', 'license', 'permit'],
                   'Permits and certificates required to process and sell the product.',
                   'List the food-safety, health, veterinary and trading permits you need, which you hold, and when pending ones '
                   'are expected. Attach copies.',
                   'Are you allowed to produce and sell this product today?'),
            _c('management_experience'),
            _c('business_viability'),
        ]),
    dict(
        id='startup-early-stage', name='Start-up / early-stage', version=TEMPLATES_VERSION, basis='generic',
        description='For new businesses with little or no sales yet, where traction and a clear use of funds matter most.',
        best_for='Businesses less than two years old, pilots, product launches.',
        source_note=SOURCE_NOTE_GENERIC,
        criteria=[
            _c('owner_contribution_pct', threshold=5, weight=1),
            _c('market_demand', mandatory=True, weight=2),
            _extra('traction', 'Early traction',
                   ['pilot', 'prototype', 'first customers', 'letter of intent', 'waiting list', 'pre-order', 'pre-orders',
                    'early sales', 'traction', 'beta', 'trial customers'],
                   'Proof that real people want this: pilots, pre-orders, waiting lists or first sales.',
                   'Show what you have already achieved: number of pilot customers, pre-orders, sign-ups or first revenue, with dates. '
                   'Numbers beat adjectives.',
                   'What have real customers already done, not just said?', weight=2),
            _extra('use_of_funds', 'Clear use of funds',
                   ['use of funds', 'use of proceeds', 'budget', 'allocation of funds', 'funds will be used'],
                   'An itemised budget showing exactly what the money buys.',
                   'Add a table: each item, its cost, and the quotation or basis for it, adding up to the amount requested. '
                   'Separate one-off costs from running costs.',
                   'Exactly what will you spend the money on?', mandatory=True, weight=2),
            _extra('milestones', 'Milestones and timeline',
                   ['milestone', 'timeline', 'roadmap', 'phase 1', 'quarter', 'month 3', 'month 6'],
                   'Dated milestones that show what happens when, and how progress will be measured.',
                   'List 4-8 milestones with dates and measurable results (for example "first 50 paying customers by month 6").',
                   'How will we know in six months whether this is working?'),
            _extra('team', 'Founders and team',
                   ['founder', 'co-founder', 'our team', 'team members', 'skills', 'experience'],
                   'Who is building this and why they can deliver it.',
                   'Introduce each founder and key team member with relevant experience, and say how time is committed '
                   '(full-time or part-time). Name any critical skill you still need to hire or partner for.',
                   'Who does what, and who is working on this full-time?'),
            _c('competitor_analysis'),
            _c('cash_flow', keywords=['cash flow', 'cashflow', 'working capital', 'runway', 'burn rate', 'monthly projection'],
               advice='Show monthly cash needs until the business breaks even and how long (in months) the funding lasts - your "runway".'),
            _c('compliance'),
            _c('business_viability'),
        ]),
    dict(
        id='services-retail', name='Retail, trading and services', version=TEMPLATES_VERSION, basis='generic',
        description='For shops, trading, transport and service businesses where location, pricing and stock control drive results.',
        best_for='Retail, wholesale, salons, workshops, logistics, hospitality.',
        source_note=SOURCE_NOTE_GENERIC,
        criteria=[
            _c('operating_margin', threshold=10, weight=2),
            _c('funding_to_contribution', threshold=5, weight=1),
            _c('owner_contribution_pct', threshold=10, mandatory=True, weight=2),
            _c('market_demand', mandatory=True, weight=2),
            _extra('location_premises', 'Premises and location',
                   ['lease', 'rental agreement', 'premises', 'location', 'foot traffic', 'shop', 'workshop'],
                   'Where you operate, on what terms, and why the location suits your customers.',
                   'State the address or area, whether you rent or own, the lease length and rent, and what makes the location '
                   'work (passing trade, access, proximity to customers). Attach the lease or offer letter.',
                   'Do you have secure premises for the whole funding period?'),
            _extra('pricing_stock', 'Pricing and stock control',
                   ['pricing', 'price list', 'mark-up', 'markup', 'inventory', 'stock control', 'stock levels'],
                   'How you price, how much stock you carry and how you keep it under control.',
                   'Show your pricing logic (cost plus mark-up or market price), typical stock levels and turnover, and how you '
                   'prevent losses and dead stock.',
                   'How do you set prices, and how much money is tied up in stock?'),
            _c('competitor_analysis'),
            _c('supplier_quotations'),
            _c('cash_flow', weight=2),
            _c('compliance', keywords=['trading licence', 'business licence', 'licence', 'license', 'registration',
                                       'tax clearance', 'compliance', 'permit']),
            _c('management_experience'),
            _c('business_viability'),
        ]),
]

from .published import PUBLISHED_PACKS  # noqa: E402

TEMPLATES = TEMPLATES + PUBLISHED_PACKS
_BY_ID = {t['id']: t for t in TEMPLATES}

_METRIC_NAMES = {
    'margin': 'Operating margin', 'funding_to_contribution': 'Funding compared with your contribution',
    'owner_contribution_pct': 'Your share of total project cost', 'revenue': 'Revenue', 'expenses': 'Expenses',
    'profit': 'Profit', 'funding': 'Funding requested', 'contribution': 'Your contribution',
    'expense_to_revenue_ratio': 'Expenses compared with revenue',
}
_PCT = {'margin', 'owner_contribution_pct'}
_RATIO = {'funding_to_contribution', 'expense_to_revenue_ratio'}
_CMP_WORDS = {'>=': 'at least', '>': 'more than', '<=': 'at most', '<': 'less than'}


def get_template(template_id: str) -> Optional[dict]:
    return _BY_ID.get(template_id)


def requirement_text(c: dict) -> str:
    """A plain-language statement of what a criterion asks for."""
    if c['kind'] == 'numeric':
        t = c.get('threshold')
        unit = '%' if c['metric'] in _PCT else 'x' if c['metric'] in _RATIO else ''
        return f"{_METRIC_NAMES.get(c['metric'], c['metric'])} {_CMP_WORDS.get(c['comparator'], c['comparator'])} {t:g}{unit}"
    if c['kind'] == 'evidence':
        return f"Your plan should cover: {c['label'].lower()}"
    return 'A reviewer will judge this; we only add a note'


def criteria_for(template: dict) -> list[dict]:
    """Criteria in the shape fundinglens_core.analysis expects (deep copy, safe to mutate)."""
    return copy.deepcopy(template['criteria'])


def criterion_guidance(template: dict) -> dict[str, dict]:
    """key -> guidance shown to the applicant."""
    out = {}
    for c in template['criteria']:
        out[c['key']] = {
            'requirement': requirement_text(c),
            'look_for': list(c.get('keywords') or []) if c['kind'] == 'evidence' else [],
            'advice': c.get('advice', ''), 'asks': c.get('asks', ''),
        }
    return out


def public_view(template: dict) -> dict:
    """What the applicant sees before running a check. Weights are deliberately not exposed."""
    g = criterion_guidance(template)
    return {
        'id': template['id'], 'name': template['name'], 'description': template['description'],
        'best_for': template.get('best_for', ''), 'basis': template['basis'], 'version': template['version'],
        'source_note': template['source_note'],
        'funder': template.get('funder'), 'sources': copy.deepcopy(template.get('sources', [])),
        'retrieved': template.get('retrieved'), 'review_status': template.get('review_status'),
        'attachments': copy.deepcopy(template.get('attachments', [])),
        'self_checks': copy.deepcopy(template.get('self_checks', [])),
        'notes': copy.deepcopy(template.get('notes', [])),
        'criteria': [{'key': c['key'], 'label': c['label'], 'kind': c['kind'], 'required': bool(c['mandatory']),
                      'requirement': g[c['key']]['requirement'], 'look_for': g[c['key']]['look_for']}
                     for c in template['criteria']],
    }


def list_public() -> list[dict]:
    return [public_view(t) for t in TEMPLATES]


def validate_templates() -> list[str]:
    """Self-check used by tests: returns a list of problems (empty = fine)."""
    from . import analysis as A
    problems = []
    ids = set()
    for t in TEMPLATES:
        if t['basis'] not in ('generic', 'published', 'funder'):
            problems.append(f"{t['id']}: bad basis")
        if t['basis'] == 'published':
            if not t.get('funder') or not t.get('retrieved'):
                problems.append(f"{t['id']}: published pack needs funder and retrieved date")
            if not t.get('sources') or any(not str(x.get('url', '')).startswith('https://') for x in t['sources']):
                problems.append(f"{t['id']}: published pack needs https sources")
            blob = ' '.join([t['description'], t['source_note'], t.get('best_for', '')]).lower()
            for bad in ('endorsed by', 'approved by', 'likely to be approved', 'guarantee', 'official ceda'):
                if bad in blob and 'not produced, reviewed or endorsed' not in blob:
                    problems.append(f"{t['id']}: implies endorsement ({bad})")
            if any(c['kind'] == 'numeric' for c in t['criteria']):
                problems.append(f"{t['id']}: published pack must not invent numeric thresholds")
        if t['id'] in ids:
            problems.append(f"duplicate template id {t['id']}")
        ids.add(t['id'])
        keys = set()
        for c in t['criteria']:
            if c['key'] in keys:
                problems.append(f"{t['id']}: duplicate criterion {c['key']}")
            keys.add(c['key'])
            if c['kind'] not in A.CRITERION_KINDS:
                problems.append(f"{t['id']}/{c['key']}: bad kind")
            if c['kind'] == 'numeric':
                if c.get('metric') not in A.METRIC_KEYS:
                    problems.append(f"{t['id']}/{c['key']}: bad metric")
                if c.get('comparator') not in A.COMPARATORS:
                    problems.append(f"{t['id']}/{c['key']}: bad comparator")
                if c.get('threshold') is None:
                    problems.append(f"{t['id']}/{c['key']}: missing threshold")
            if c['kind'] == 'evidence' and not c.get('keywords'):
                problems.append(f"{t['id']}/{c['key']}: evidence criterion without keywords")
            if c['kind'] == 'qualitative' and c.get('weight'):
                problems.append(f"{t['id']}/{c['key']}: qualitative must have weight 0")
            if not c.get('advice') or not c.get('asks'):
                problems.append(f"{t['id']}/{c['key']}: missing advice or reviewer question")
    return problems
