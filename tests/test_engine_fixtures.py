"""Regression tests on realistic sample plans (tests/fixtures). Each test pins a behaviour found while testing the engine."""
import unittest
from pathlib import Path

from fundinglens_core import analysis as A, readiness as R, templates as T

FX = Path(__file__).parent / 'fixtures'


def run(name, tid='ceda-agri', funding=500_000, contribution=100_000):
    t = T.get_template(tid)
    det = A.analyse_document((FX / name).read_text(), funding, contribution, T.criteria_for(t))
    return t, det, A.build_result(det, None, {'mode': 'rules_only', 'message': ''})


def states(res):
    return {c['key']: R.criterion_state(c) for c in res['rubric']['criteria']}


class FixtureTests(unittest.TestCase):
    def test_strong_plan_is_mostly_covered_and_figures_read(self):
        _, det, res = run('strong_agri.txt')
        m = det['metrics']
        self.assertEqual((m['revenue'], m['expenses']), (2_150_000, 1_590_000))
        q = R.quick_scan(res)['counts']
        self.assertGreaterEqual(q['covered'], 22)
        self.assertLessEqual(q['gaps'], 2)

    def test_strong_plan_missing_cost_table_is_still_reported(self):
        _, _, res = run('strong_agri.txt')
        self.assertEqual(states(res)['ceda_project_costs'], 'missing')

    def test_owners_contribute_wording_counts_for_financing_plan(self):
        _, _, res = run('strong_agri.txt')
        self.assertEqual(states(res)['ceda_financing_plan'], 'mentioned')

    def test_amount_in_plan_differs_from_entered_amount_is_flagged(self):
        _, det, _ = run('strong_agri.txt', funding=500_000, contribution=250_000)
        titles = [r['title'] for r in det['risks']]
        self.assertTrue(any('funding request in your plan differs' in t for t in titles), titles)

    def test_matching_amounts_are_not_flagged(self):
        _, det, _ = run('table_style.txt', funding=500_000, contribution=125_000)
        self.assertFalse([r for r in det['risks'] if 'differs' in r['title']])

    def test_label_on_one_line_value_on_next(self):
        _, det, _ = run('messy_pdf.txt')
        self.assertEqual(det['metrics']['expenses'], 940_000)
        self.assertEqual(det['metrics']['revenue'], 1_200_000)

    def test_table_with_pipes_and_space_thousands(self):
        _, det, _ = run('table_style.txt')
        self.assertEqual((det['metrics']['revenue'], det['metrics']['expenses']), (1_800_000, 1_350_000))

    def test_loan_requested_and_owners_apostrophe_labels(self):
        self.assertEqual(A.extract_amount('Loan requested | 500 000', A.FUNDING_LABELS)[0], 500_000)
        self.assertEqual(A.extract_amount("Owner's contribution | 125 000", A.CONTRIBUTION_LABELS)[0], 125_000)
        self.assertEqual(A.extract_amount('Owner’s contribution: P125,000', A.CONTRIBUTION_LABELS)[0], 125_000)

    def test_weak_plan_is_needs_work_with_no_invented_figures(self):
        _, det, res = run('weak_vague.txt')
        self.assertIsNone(det['metrics']['revenue'])
        self.assertEqual(R.quick_scan(res)['band'], 'needs_work')
        self.assertGreaterEqual(R.quick_scan(res)['counts']['gaps'], 20)

    def test_if_any_competitors_does_not_count_as_analysis(self):
        a, n = A.keyword_hits('Our competitors, if any, are not known.', ['competitor'])
        self.assertEqual((a, n), (0, 1))

    def test_no_competition_is_negated(self):
        self.assertEqual(A.keyword_hits('We have no competition.', ['competition']), (0, 1))

    def test_contradiction_note_when_some_mentions_are_negative(self):
        _, _, res = run('keyword_traps.txt')
        t = T.get_template('ceda-agri')
        rep = R.applicant_report(res, t)
        cf = [i for i in rep['items'] if i['key'] == 'ceda_cash_flow'][0] if 'key' in rep['items'][0] else None
        if cf:
            self.assertIn('contradict', cf['detail'])

    def test_applicant_report_never_uses_officer_wording(self):
        for f in FX.glob('*.txt'):
            _, _, res = run(f.name)
            blob = str(R.applicant_report(res, T.get_template('ceda-agri'))).lower()
            self.assertNotIn('an officer', blob, f.name)
            self.assertNotIn('institution', blob, f.name)

    def test_every_template_handles_every_fixture(self):
        for t in T.TEMPLATES:
            for f in FX.glob('*.txt'):
                det = A.analyse_document(f.read_text(), 500_000, 100_000, T.criteria_for(t))
                res = A.build_result(det, None, {'mode': 'rules_only', 'message': ''})
                R.applicant_report(res, t)
                R.quick_scan(res)

    def test_year_numbers_are_not_amounts(self):
        self.assertEqual(A.extract_amount('Revenue for Year 1 is projected at P 1 200 000.', A.REVENUE_LABELS)[0], 1_200_000)
        self.assertEqual(A.extract_amount('Total revenue (Year 1): BWP 1,200,000', A.REVENUE_LABELS)[0], 1_200_000)

    def test_monthly_amounts_are_annualised_for_revenue_and_expenses(self):
        self.assertEqual(A.extract_amount('Expenses are about P 80k per month', A.EXPENSE_LABELS, annualise=True)[0], 960_000)
        self.assertEqual(A.extract_amount('Expenses are about P 80k per month', A.EXPENSE_LABELS)[0], 80_000)

    def test_value_after_blank_line(self):
        self.assertEqual(A.extract_amount('Revenue\n\nP 1,200,000', A.REVENUE_LABELS)[0], 1_200_000)

    def test_label_does_not_borrow_a_following_sentence_or_heading(self):
        self.assertIsNone(A.extract_amount('Total revenue\nCost of goods sold\nP 500,000', A.REVENUE_LABELS)[0])


if __name__ == '__main__':
    unittest.main()
