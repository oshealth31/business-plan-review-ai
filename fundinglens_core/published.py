"""Published-guideline packs for FundingLens Check.

A pack here is built ONLY from material a funder has made public (application forms, checklists, FAQs).
It is not produced, reviewed or endorsed by the funder, and it is never a prediction of a decision.

What a pack can and cannot do (design rules, enforced by tests/test_published.py):
  * `criteria`      - checks the PLAN TEXT can answer: "does the plan cover what the funder's business-plan form asks for?"
                      These are keyword/coverage checks, never proof of quality.
  * `attachments`   - documents the funder's checklist asks you to attach. Software cannot see attachments, so these are a
                      "prepare before you submit" list and are never scored.
  * `self_checks`   - eligibility statements only the applicant can confirm.
  * `notes`         - other published facts worth knowing, each with the year/source, flagged as possibly out of date.
  * No numeric thresholds are invented. If a funder has not published a number, there is no number here.
  * Every pack carries its sources, the date we last read them, and a review status.

Source material read on 2026-10-05 (automated reading of the public documents - a human must compare this file with the
originals before it is offered to paying users; see docs/PUBLISHED_PACKS.md).
"""
from __future__ import annotations

from typing import Any

PACKS_VERSION = '2026.10.1'
RETRIEVED = '2026-10-05'
CEDA = 'Citizen Entrepreneurial Development Agency (CEDA), Botswana'

_BASE = 'https://www.ceda.co.bw'
SRC_FORM = dict(title='CEDA Business Plan Form', url=f'{_BASE}/sites/default/files/ceda-business-plan-form.pdf',
                note='13-page form; no version or date shown')
SRC_AGRI = dict(title='CEDA Agri Business Loan Checklist', url=f'{_BASE}/sites/default/files/Agri%20Business%20Loan%20Checklist_0.pdf',
                note='"Effective 20-02-17"')
SRC_SERV = dict(title='CEDA Services Loan Checklist', url=f'{_BASE}/sites/default/files/Services%20Loan%20Checklist.pdf',
                note='"Effective 20-02-17"')
SRC_MANU = dict(title='CEDA Manufacturing Loan Checklist', url=f'{_BASE}/sites/default/files/Manufacturing%20Loan%20Checklist%20-%20replace.pdf',
                note='"Effective 20-02-17"')
SRC_GEN = dict(title='CEDA Loan Application Checklist (general)', url=f'{_BASE}/sites/default/files/form_checklist.pdf',
               note='no version or date shown')
SRC_FAQ = dict(title="CEDA FAQ's", url=f'{_BASE}/faq-s', note='web page; no date shown')
SRC_GUIDE = dict(title='Revised CEDA loan guidelines (2020), third-party copy',
                 url='https://www.grantthornton.co.bw/globalassets/1.-member-firms/botswana/insights_pdfs/tax_alert/2020-07-24-revised-ceda-loan-guidelines.pdf',
                 note='published July 2020; COVID-era measures in it have expired')

SOURCE_NOTE = ('Built from CEDA\'s publicly available forms and checklists (read on 5 October 2026). It is not produced, '
               'reviewed or endorsed by CEDA, it does not predict CEDA\'s decision, and CEDA may have changed its requirements - '
               'always use CEDA\'s current forms and ask CEDA if unsure.')


def _ev(key: str, label: str, keywords: list[str], description: str, advice: str, asks: str, *,
        mandatory: bool = False, weight: float = 1.0) -> dict[str, Any]:
    return dict(key=key, label=label, kind='evidence', keywords=keywords, description=description, advice=advice, asks=asks,
                mandatory=mandatory, weight=2.0 if mandatory else weight, enabled=True)


def _viability() -> dict[str, Any]:
    return dict(key='ceda_viability', label='Viable, sustainable and repaid from the project', kind='qualitative', weight=0.0,
                mandatory=False, keywords=[], enabled=True,
                description=('CEDA\'s FAQ says a project "must be viable, sustainable and adding value to the economy" and that '
                             'repayment has to come from the project and not from other sources. (reviewer judgement)'),
                advice='Show, with numbers, that the project\'s own cash flow can pay the instalments, and say who benefits and how '
                       '(jobs, local supply, new products).',
                asks='Can the project itself repay this loan, and does it add value to the economy?')


def _common_criteria() -> list[dict[str, Any]]:
    """Plan content that CEDA's Business Plan Form asks for. Section numbers refer to that form's layout."""
    return [
        _ev('ceda_project_costs', 'Project capital costs (item by item)',
            ['project cost', 'capital cost', 'total project cost', 'cost of machinery', 'cost of equipment', 'cost of land',
             'cost of building', 'working capital', 'installation', 'technical assistance'],
            'The form asks for the cost of land, buildings, machinery, transport, furniture and fixtures, installation, technical '
            'assistance, working capital and other costs, with a total.',
            'Add a table of every cost item with its amount and a total. Use the same figures as your quotations, and show working '
            'capital separately.',
            'What exactly does the project cost, item by item?', mandatory=True),
        _ev('ceda_financing_plan', 'Financing plan and your own contribution',
            ['owner contribution', 'owner\'s contribution', 'own contribution', 'we contribute', 'owners contribute', 'contribute p', 'financing plan',
             'source of funds', 'sources of funds', 'contribution in cash', 'total project financing', 'overdraft'],
            'The form asks for the owner\'s contribution (cash and assets), other loans or overdrafts, the amount requested from '
            'CEDA, and a total that matches the project cost.',
            'State your contribution in money terms, split into cash and assets (with values), list any other loans or overdrafts, '
            'then the amount you are asking for. The total must equal the project cost.',
            'How is the whole project paid for, and how much of your own money is in it?', mandatory=True),
        _ev('ceda_management_team', 'Management team and experience',
            ['management team', 'managers', 'directors', 'years of experience', 'experience in', 'curriculum vitae', 'qualifications',
             'track record'],
            'The form asks for each manager\'s name and their experience and suitability for this business.',
            'Name each person who will run the business, with relevant years of experience and results, and attach CVs and '
            'certificates.',
            'Who will run this business and why are they suited to it?', mandatory=True),
        _ev('ceda_location', 'Project location and premises',
            ['plot', 'location', 'premises', 'lease agreement', 'title deed', 'land board', 'rental'],
            'The form asks for the project location, plot number and any lease agreement.',
            'Give the location and plot number, say whether you own or lease it, and for how long. Attach the title deed or lease '
            '(a lease should cover the loan repayment period).',
            'Where will the project operate and do you have secure use of the site?'),
        _ev('ceda_operations', 'How the business operates (production or service delivery)',
            ['production process', 'production capacity', 'raw material', 'finished goods', 'capacity', 'service delivery',
             'plant life', 'equipment replacement'],
            'The form asks for a clear description from raw material to finished goods, maximum capacity and equipment life, how '
            'production builds up, and production risks.',
            'Describe the process step by step, the maximum capacity, how output grows in the first years, when equipment will be '
            'replaced and what could disrupt production and how you would handle it.',
            'How does the business actually work, and what is its capacity?'),
        _ev('ceda_target_market', 'Target market and market size',
            ['target market', 'market size', 'customers', 'who will buy', 'demand', 'potential clients'],
            'The form asks who you will sell to, how many products or services could be sold, and at what price.',
            'Name your customer groups, estimate how many units you could sell at what price, and say how you arrived at the '
            'estimate (survey, orders, sales records).',
            'Who will buy, how many, and at what price?', mandatory=True),
        _ev('ceda_competitors', 'Competitors and market share',
            ['competitor', 'competition', 'market share', 'current suppliers'],
            'The form asks who currently supplies the market, their market share and prices, and the share you aim to capture.',
            'List your main competitors with their prices and estimated share, and state the share you expect to reach and why '
            'it is realistic.',
            'Who else sells to these customers, and what share can you realistically win?'),
        _ev('ceda_marketing', 'Marketing strategy, promotion and distribution',
            ['marketing', 'promotion', 'advertis', 'distribution', 'channels', 'deliver to', 'sales channel'],
            'The form asks how you differ from competitors, how customers will hear about you, and how the product reaches buyers.',
            'Explain how you will win customers (price, quality, service), how they will learn about you, and how products or '
            'services get to them.',
            'Why will customers buy from you, and how will they find and receive your product?'),
        _ev('ceda_suppliers', 'Supply of materials and suppliers',
            ['supplier', 'suppliers', 'raw material', 'source of stock', 'supply chain', 'procure'],
            'The form asks where products or raw materials come from, how many suppliers there are and how reliable they are.',
            'Name your suppliers, say how reliable they are, what happens if one fails, and whether there is a cheaper source.',
            'Where do your inputs come from, and what if a supplier lets you down?'),
        _ev('ceda_pricing', 'Pricing and profit per sale',
            ['selling price', 'pricing', 'profit per', 'mark-up', 'markup', 'cost price', 'gross margin', 'unit price'],
            'The form asks for competitors\' prices, your selling price and the profit on each sale (selling price less cost price).',
            'Show your price next to competitors\' prices and the cost and profit per unit.',
            'What do you charge, what does it cost you, and what is left?'),
        _ev('ceda_implementation', 'Implementation schedule',
            ['implementation', 'schedule', 'timeline', 'start date', 'milestone', 'activities'],
            'The form asks when the project starts, the first step, and the activities after that with reasonable dates.',
            'Add a dated list of activities from approval to full operation, beginning with the first thing that must happen.',
            'What happens when, and what comes first?'),
        _ev('ceda_benefits', 'Benefits: jobs, community and economy',
            ['employment', 'jobs', 'create jobs', 'community', 'benefit', 'economy', 'local'],
            'The form asks why this is a good project, who it helps, how much employment it creates and how the community and '
            'economy are better off.',
            'State the number of jobs created, who benefits, and any local suppliers or customers that gain.',
            'Why is this a good project for Botswana, and who benefits?'),
        _ev('ceda_staff_training', 'Staffing, wages and training',
            ['wages', 'salaries', 'employees', 'staff', 'training', 'skills required'],
            'The form asks how many people you will employ, the skills and wages, and training for staff and for you.',
            'List roles, numbers, skills and wages, and any training you plan with its cost.',
            'Who will you employ, at what cost, and are they trained?'),
        _ev('ceda_projections', 'Financial projections (trading results, balance sheet)',
            ['five year', '5 year', '5-year', 'income statement', 'balance sheet', 'trading results', 'projected', 'projections',
             'year 1', 'year 5'],
            'CEDA\'s sector checklists ask for projected balance sheet, income statement and cash flows for 5 years (its general '
            'checklist says at least 3).',
            'Include projected trading results and balance sheets for each of the first five years (follow the checklist for your '
            'sector), with the assumptions behind them.',
            'What will the business earn and own each year for five years?', mandatory=True),
        _ev('ceda_cash_flow', 'Cash-flow projection',
            ['cash flow', 'cashflow', 'cash-flow', 'net cash', 'loan repayments', 'cash inflow'],
            'The form asks for projected cash flows including loan repayments, taxation and asset purchases.',
            'Add a cash-flow table for the same years showing money in, money out, loan repayments and the closing balance.',
            'Will there be enough cash each year to pay the instalments?', mandatory=True),
        _ev('ceda_assumptions', 'Assumptions behind the numbers',
            ['assumption', 'assumptions', 'assumed', 'depreciation rate', 'tax rate', 'sales price', 'variable cost'],
            'The form asks for sales units, sales price, variable costs, overheads, depreciation and tax rates, and other assumptions.',
            'List each assumption (units, price, costs, depreciation, tax) in one place so a reader can check the projections.',
            'What are your figures based on?'),
        _ev('ceda_risks', 'Risk statement',
            ['risk', 'risks', 'mitigat', 'overrun', 'environmental impact', 'market penetration'],
            'The form asks for a risk statement covering capital cost overruns, limited market penetration, labour and technical '
            'risks, and environmental impact where necessary.',
            'List the main risks (cost overruns, slower sales, staffing/technical problems, environmental impact if relevant) and '
            'what you will do about each.',
            'What could go wrong, and what is your plan if it does?', mandatory=True),
        _ev('ceda_sensitivity', 'Sensitivity analysis and insurance',
            ['sensitivity', 'what if', 'insured', 'insurance', 'succession', 'spares', 'worst case'],
            'The form asks what could stop you succeeding, whether machinery and the owner are insured, who could take over if you '
            'are ill, whether spares are available and what would stop you selling the planned amount.',
            'Show what happens to profit and cash flow if sales fall or costs rise, and cover insurance, succession and spares.',
            'How robust is the plan if sales are lower or costs higher?'),
        _ev('ceda_swot', 'SWOT summary',
            ['swot', 'strengths', 'weaknesses', 'opportunities', 'threats'],
            'The form asks for a SWOT summary.',
            'Add a short SWOT: what you do better than competitors, strengths, weaknesses, where else you can grow, and threats.',
            'What are your strengths and weaknesses, honestly?', mandatory=True),
        _ev('ceda_security', 'Security offered',
            ['security', 'collateral', 'forced sale', 'guarantee', 'title deed', 'life insurance'],
            'The form asks you to describe the security you offer, with age, cost, market value and estimated forced-sale value.',
            'List each asset offered as security with its description, cost, value and forced-sale value, and attach valuation or '
            'title documents.',
            'What can the lender fall back on, and what is it worth if sold quickly?'),
        _ev('ceda_quotations', 'Quotations for items to be financed',
            ['quotation', 'quotations', 'quote'],
            'CEDA\'s checklists ask for three quotations for the items to be financed.',
            'Get three current quotations for each major item, make your cost table match the one you choose, and say why.',
            'Where do your cost figures come from? Can I see three quotations?'),
        _ev('ceda_letters_of_intent', 'Letters of intent or contracts from potential clients',
            ['letter of intent', 'letters of intent', 'contract with', 'purchase order', 'supply agreement', 'standing order'],
            'CEDA\'s checklists ask for three letters of intent or contracts from potential clients.',
            'Collect three signed letters of intent or contracts that name the client, the products, volumes and prices, and refer '
            'to them in the market section.',
            'Which real customers have committed to buy?'),
        _ev('ceda_licences_tax', 'Licences, registration and tax clearance',
            ['licence', 'license', 'trading licence', 'registration', 'registered', 'tax clearance', 'permit'],
            'CEDA\'s checklists ask for a copy of the licence needed to operate and, where applicable, a tax clearance certificate.',
            'List the licences and permits your business needs, which you hold (with numbers or dates) and which are pending.',
            'Is the business allowed to operate legally today?'),
        _viability(),
    ]


def _agri_extra() -> list[dict[str, Any]]:
    return [_ev('ceda_land_water', 'Land and water for the project',
                ['land allocation', 'land board', 'title deed', 'tribal land', 'borehole', 'soil test', 'water test', 'water source',
                 'irrigation', 'land use'],
                'The agri checklist asks for proof of ownership or availability of land, land use in line with the business, '
                'soil and water tests (horticulture and dry-land farming) and borehole documents.',
                'State the land (plot, tenure, size), show the land use matches your plan, and describe water source, borehole '
                'and test results.',
                'Do you have the right to use this land, and is there enough water?')]


ATT_COMMON: list[dict[str, str]] = [
    dict(item='Completed CEDA application form and business plan form', when='always'),
    dict(item='Certified copies of Omang (individuals, partners, shareholders and directors)', when='always'),
    dict(item='Resolution by the Board of Directors to apply for a loan', when='companies'),
    dict(item='Form 2 (list of shareholders/directors); Form 3 (certificate of incorporation); Form 4 (allotment of shares) and share certificates',
         when='companies'),
    dict(item='Memorandum and Articles of Association', when='companies incorporated before the Companies Act, 2003'),
    dict(item='Audited financial statements for at least 3 years', when='existing operations'),
    dict(item='Personal bank statements for 12 months', when='start-ups and/or individual directors'),
    dict(item='Financial projections (balance sheet, income statement, cash flows) for 5 years', when='always'),
    dict(item='Personal balance sheets of all shareholders or owners', when='always'),
    dict(item='Valuation report of existing assets by a professional valuer (not older than 12 months)', when='existing assets'),
    dict(item='Proof of title deed for the property to be purchased or used as security', when='always'),
    dict(item='Due diligence report valid for 12 months', when='existing operations'),
    dict(item='Deed of sale of business', when='buying an existing business'),
    dict(item='Three quotations for the items to be financed', when='always'),
    dict(item='Insurance quotations for the assets to be financed', when='always'),
    dict(item='Letters of intent / contracts from potential clients (3)', when='always'),
    dict(item='Curriculum vitae and professional/academic certificates of shareholders or owners', when='always'),
    dict(item='Copy of the licence(s) needed to operate the business', when='where necessary'),
    dict(item='Tax clearance certificate', when='where applicable'),
    dict(item='Lease agreement or provisional lease agreement', when='leased premises'),
    dict(item='Franchise agreement', when='where applicable'),
    dict(item='Certified marriage certificate; Deed of Marriage Instrument (Form A or Form B)', when='where applicable'),
    dict(item='Environmental Impact Assessment report', when='where necessary'),
]
ATT_AGRI: list[dict[str, str]] = [
    dict(item='Provisional offer of land allocation', when='young farmers'),
    dict(item='Proof of ownership or availability of land; land use in line with the proposed business', when='always'),
    dict(item='Livestock brand certificate', when='where applicable'),
    dict(item='Soil and water tests report', when='horticulture and dry-land farming'),
    dict(item='Borehole drilling completion certificate and proof of ownership', when='where applicable'),
    dict(item='Consent from the Land Board to reticulate water from one plot to another', when='where applicable'),
    dict(item='Bills of quantity', when='where applicable'),
]
ATT_BUILD: list[dict[str, str]] = [
    dict(item='Structural report by a certified structural engineer (not older than 2 years)', when='property development'),
    dict(item='Bills of quantity from a registered quantity surveyor', when='property development'),
    dict(item='Approved architectural drawings / concept of approved plans', when='property development'),
    dict(item='Three quotations for the proposed development, with contractor documents and profiles (e.g. PPADB registration, tax clearance)',
         when='property development'),
    dict(item='Soil test report', when='where necessary'),
]
SELF_CHECKS: list[dict[str, str]] = [
    dict(text='Every shareholder, partner, director or individual applicant is a citizen aged 18 or over.', source='CEDA loan checklists'),
    dict(text='The project is viable, sustainable and adds value to the economy.', source="CEDA FAQ's"),
    dict(text='Repayment will come from the project itself, not from other sources.', source="CEDA FAQ's"),
    dict(text='You are asking for a whole project, not one asset: boreholes or tractors alone are not projects, but can be components of one.',
         source="CEDA FAQ's"),
    dict(text='Your activity is in a sector CEDA finances (agri-business, property, manufacturing and services) and is a start-up or an expansion.',
         source="CEDA FAQ's"),
]
NOTES: list[dict[str, str]] = [
    dict(text='Loan size and security (2020 guidelines): mainline limits were P1,000,000 for small/micro, P10,000,000 for medium and '
              'P50,000,000 for large projects, and security was mandatory above P5,000,000. These figures are from 2020 - check '
              'CEDA\'s current limits before relying on them.', source='Revised CEDA loan guidelines (2020)'),
    dict(text='CEDA\'s general checklist asks for financial projections for "at least three years"; its sector checklists ask for 5 years. '
              'Follow the checklist for your sector.', source='CEDA checklists'),
]


def _pack(pid: str, name: str, sector_sources: dict, extra_criteria: list, extra_att: list, description: str, best_for: str) -> dict[str, Any]:
    return dict(
        id=pid, name=name, version=PACKS_VERSION, basis='published', funder=CEDA, description=description, best_for=best_for,
        source_note=SOURCE_NOTE, retrieved=RETRIEVED, review_status='needs_human_review',
        sources=[SRC_FORM, sector_sources, SRC_GEN, SRC_FAQ, SRC_GUIDE],
        criteria=_common_criteria() + extra_criteria,
        attachments=ATT_COMMON + extra_att, self_checks=SELF_CHECKS, notes=NOTES)


PUBLISHED_PACKS: list[dict[str, Any]] = [
    _pack('ceda-agri', 'CEDA mainline loan - agri-business (from CEDA\'s published forms)', SRC_AGRI, _agri_extra(), ATT_AGRI,
          'Checks whether your business plan covers what CEDA\'s published Business Plan Form asks for, and lists the documents on '
          'CEDA\'s published Agri Business Loan Checklist.',
          'Farming, horticulture, livestock and agri-processing projects applying to CEDA.'),
    _pack('ceda-manufacturing', 'CEDA mainline loan - manufacturing (from CEDA\'s published forms)', SRC_MANU, [], ATT_BUILD,
          'Checks whether your business plan covers what CEDA\'s published Business Plan Form asks for, and lists the documents on '
          'CEDA\'s published Manufacturing Loan Checklist.',
          'Manufacturing and processing projects applying to CEDA.'),
    _pack('ceda-services', 'CEDA mainline loan - services (from CEDA\'s published forms)', SRC_SERV, [], ATT_BUILD,
          'Checks whether your business plan covers what CEDA\'s published Business Plan Form asks for, and lists the documents on '
          'CEDA\'s published Services Loan Checklist.',
          'Service businesses (including property-related services) applying to CEDA.'),
]
