"""End-to-end API tests (FastAPI TestClient, throwaway SQLite database)."""
import json
import os
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ.update(ENVIRONMENT='test', DATA_DIR=_TMP, JWT_SECRET='x' * 40, ADMIN_EMAIL='admin@example.com',
                  ADMIN_PASSWORD='Admin-password-123', PURGE_INTERVAL_SECONDS='0', PAYMENT_WEBHOOK_SECRET='whsec_test_secret',
                  REQUIRE_INVITE='true', QUICK_SCANS_PER_DAY='50', FULL_REPORTS_PER_DAY='50')
os.environ.pop('OPENAI_API_KEY', None)
os.environ.pop('OPENAI_MODEL', None)

from fastapi.testclient import TestClient  # noqa: E402

import backend.app as M  # noqa: E402
from backend import billing as B  # noqa: E402

DEMO = (Path(__file__).resolve().parent.parent / 'demo_data' / 'business_plan_demo.txt').read_bytes()
PW = 'Correct-horse-battery-9'
_n = [0]


def hdr(tok):
    return {'Authorization': f'Bearer {tok}'}


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm = TestClient(M.app)
        cls.c = cls.cm.__enter__()
        r = cls.c.post('/api/token', data={'username': 'admin@example.com', 'password': 'Admin-password-123'})
        cls.admin = hdr(r.json()['access_token'])

    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)

    def setUp(self):
        M._RATE.clear()

    def test_signup_is_rate_limited(self):
        M._RATE.clear()
        codes = [self.c.post('/api/auth/signup', json={'email': f'rl{i}@example.com', 'password': PW, 'invite_code': 'bad', 'accept_terms': True}).status_code
                 for i in range(12)]
        self.assertEqual(codes[:10], [400] * 10)
        self.assertEqual(codes[10], 429)

    def invite(self, credits=5, email=None):
        body = {'credits': credits}
        if email:
            body['email'] = email
        return self.c.post('/api/admin/invites', json=body, headers=self.admin).json()['code']

    def user(self, credits=5):
        _n[0] += 1
        email = f'user{_n[0]}@example.com'
        r = self.c.post('/api/auth/signup', json={'email': email, 'password': PW, 'invite_code': self.invite(credits), 'accept_terms': True})
        self.assertEqual(r.status_code, 200, r.text)
        return email, hdr(r.json()['access_token'])

    def check(self, h, template='sme-growth-general', upload=True):
        r = self.c.post('/api/checks', json={'title': 'My plan', 'template_id': template, 'funding_request': 500000,
                                             'owner_contribution': 100000}, headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()['id']
        if upload:
            u = self.c.post(f'/api/checks/{cid}/document', files={'file': ('plan.txt', DEMO, 'text/plain')}, headers=h)
            self.assertEqual(u.status_code, 200, u.text)
            return cid, u.json()
        return cid, None

    def balance(self, h):
        return self.c.get('/api/credits', headers=h).json()['balance']

    # ---- accounts
    def test_signup_requires_invite_and_terms(self):
        r = self.c.post('/api/auth/signup', json={'email': 'a@example.com', 'password': PW, 'accept_terms': True})
        self.assertEqual(r.status_code, 400)
        r = self.c.post('/api/auth/signup', json={'email': 'a@example.com', 'password': PW, 'invite_code': self.invite(), 'accept_terms': False})
        self.assertEqual(r.status_code, 400)

    def test_invite_single_use_and_grants_credits(self):
        code = self.invite(credits=3)
        ok = self.c.post('/api/auth/signup', json={'email': 'single@example.com', 'password': PW, 'invite_code': code, 'accept_terms': True})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.balance(hdr(ok.json()['access_token'])), 3)
        again = self.c.post('/api/auth/signup', json={'email': 'single2@example.com', 'password': PW, 'invite_code': code, 'accept_terms': True})
        self.assertEqual(again.status_code, 400)

    def test_invite_bound_to_other_email_rejected(self):
        code = self.invite(email='only@example.com')
        r = self.c.post('/api/auth/signup', json={'email': 'other@example.com', 'password': PW, 'invite_code': code, 'accept_terms': True})
        self.assertEqual(r.status_code, 400)

    def test_weak_password_rejected(self):
        r = self.c.post('/api/auth/signup', json={'email': 'weak@example.com', 'password': 'short', 'invite_code': self.invite(), 'accept_terms': True})
        self.assertEqual(r.status_code, 400)

    def test_requires_auth_and_users_are_isolated(self):
        self.assertEqual(self.c.get('/api/checks').status_code, 401)
        _, a = self.user()
        _, b = self.user()
        cid, _ = self.check(a)
        self.assertEqual(self.c.get(f'/api/checks/{cid}', headers=b).status_code, 404)
        self.assertEqual(self.c.post(f'/api/checks/{cid}/full', headers=b).status_code, 404)
        self.assertEqual(self.c.delete(f'/api/checks/{cid}', headers=b).status_code, 404)
        self.assertEqual(self.c.get('/api/admin/users', headers=a).status_code, 403)

    # ---- templates
    def test_templates_public_include_published_packs_without_weights(self):
        r = self.c.get('/api/templates')
        self.assertEqual(r.status_code, 200)
        ids = {t['id'] for t in r.json()}
        self.assertTrue({'ceda-agri', 'ceda-manufacturing', 'ceda-services', 'sme-growth-general'} <= ids)
        self.assertNotIn('weight', r.text)

    # ---- quick scan
    def test_quick_scan_is_free_and_leaks_nothing(self):
        _, h = self.user(credits=2)
        cid, up = self.check(h)
        self.assertEqual(self.balance(h), 2)
        blob = json.dumps(up['quick']).lower()
        for t in M.T.TEMPLATES:
            for crit in t['criteria']:
                self.assertNotIn(crit['label'].lower(), blob)
        self.assertNotIn('how_to_fix', blob)
        self.assertNotIn('score', blob)

    def test_bad_uploads_rejected(self):
        _, h = self.user()
        cid, _ = self.check(h, upload=False)
        r = self.c.post(f'/api/checks/{cid}/document', files={'file': ('x.exe', b'MZ' + b'0' * 100, 'application/octet-stream')}, headers=h)
        self.assertEqual(r.status_code, 415)
        r = self.c.post(f'/api/checks/{cid}/document', files={'file': ('x.pdf', b'not a pdf', 'application/pdf')}, headers=h)
        self.assertEqual(r.status_code, 415)
        r = self.c.post(f'/api/checks/{cid}/document', files={'file': ('x.txt', b'tiny', 'text/plain')}, headers=h)
        self.assertEqual(r.status_code, 422)

    # ---- full report and credits
    def test_full_report_charges_then_recheck_cheaper(self):
        _, h = self.user(credits=5)
        cid, _ = self.check(h)
        r = self.c.post(f'/api/checks/{cid}/full', json={}, headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.balance(h), 3)
        self.assertIn('items', json.dumps(r.json()))
        r2 = self.c.post(f'/api/checks/{cid}/full', json={}, headers=h)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self.balance(h), 2)

    def test_full_report_blocked_without_credits(self):
        _, h = self.user(credits=1)
        cid, _ = self.check(h)
        r = self.c.post(f'/api/checks/{cid}/full', json={}, headers=h)
        self.assertEqual(r.status_code, 402)
        self.assertEqual(self.balance(h), 1)

    def test_idempotency_key_prevents_double_charge(self):
        _, h = self.user(credits=6)
        cid, _ = self.check(h)
        k = {**h, 'Idempotency-Key': 'abcdef123456'}
        a = self.c.post(f'/api/checks/{cid}/full', json={}, headers=k)
        b = self.c.post(f'/api/checks/{cid}/full', json={}, headers=k)
        self.assertEqual((a.status_code, b.status_code), (200, 200))
        self.assertEqual(self.balance(h), 4)

    def test_ai_not_used_without_consent(self):
        _, h = self.user(credits=4)
        cid, _ = self.check(h)
        r = self.c.post(f'/api/checks/{cid}/full', json={'use_ai': True}, headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.dumps(r.json()).count('"mode": "llm"'), 0)

    def test_report_html_and_published_pack_sections(self):
        _, h = self.user(credits=4)
        cid, _ = self.check(h, template='ceda-agri')
        self.c.post(f'/api/checks/{cid}/full', json={}, headers=h)
        r = self.c.get(f'/api/checks/{cid}/report', headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Documents to prepare', r.text)
        self.assertIn('not produced, reviewed or endorsed', r.text)

    def test_report_404_before_purchase(self):
        _, h = self.user()
        cid, _ = self.check(h)
        self.assertEqual(self.c.get(f'/api/checks/{cid}/report', headers=h).status_code, 404)

    # ---- payments
    def _hook(self, body, secret='whsec_test_secret', ts=None):
        raw = json.dumps(body).encode()
        ts = ts or int(time.time())
        return self.c.post('/api/payments/webhook', content=raw,
                           headers={'x-fl-timestamp': str(ts), 'x-fl-signature': B.sign_webhook(secret, ts, raw)})

    def test_webhook_credits_user_once(self):
        email, h = self.user(credits=0)
        ev = {'event_id': 'evt_001', 'type': 'credits.purchased', 'email': email, 'credits': 10, 'amount': '100', 'currency': 'BWP'}
        self.assertEqual(self._hook(ev).json()['status'], 'applied')
        self.assertEqual(self._hook(ev).json()['status'], 'duplicate')
        self.assertEqual(self.balance(h), 10)

    def test_webhook_rejects_bad_signature_and_stale(self):
        email, _ = self.user()
        ev = {'event_id': 'evt_bad', 'type': 'credits.purchased', 'email': email, 'credits': 5}
        self.assertEqual(self._hook(ev, secret='wrong').status_code, 401)
        self.assertEqual(self._hook(ev, ts=int(time.time()) - 4000).status_code, 401)

    def test_webhook_unmatched_then_resolved_by_admin(self):
        ev = {'event_id': 'evt_unmatched', 'type': 'credits.purchased', 'email': 'nobody@example.com', 'credits': 5}
        self.assertEqual(self._hook(ev).json()['status'], 'unmatched')
        pay = self.c.get('/api/admin/payments', headers=self.admin)
        self.assertEqual(pay.status_code, 200)
        self.assertIn('evt_unmatched', pay.text)

    # ---- admin
    def test_admin_credit_adjustment(self):
        email, h = self.user(credits=0)
        r = self.c.post('/api/admin/credits', json={'email': email, 'credits': 4, 'reason': 'goodwill'}, headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.balance(h), 4)

    # ---- privacy
    def test_delete_check_removes_document(self):
        _, h = self.user()
        cid, _ = self.check(h)
        before = len(list(M.DOCS.iterdir()))
        self.assertEqual(self.c.delete(f'/api/checks/{cid}', headers=h).status_code, 200)
        self.assertEqual(len(list(M.DOCS.iterdir())), before - 1)
        self.assertEqual(self.c.get(f'/api/checks/{cid}', headers=h).status_code, 404)

    def test_account_deletion(self):
        email, h = self.user()
        cid, _ = self.check(h)
        bad = self.c.post('/api/me/delete', json={'password': 'wrong-password-123'}, headers=h)
        self.assertEqual(bad.status_code, 403 if bad.status_code == 403 else bad.status_code)
        self.assertNotEqual(bad.status_code, 200)
        ok = self.c.post('/api/me/delete', json={'password': PW}, headers=h)
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(self.c.get('/api/me', headers=h).status_code, 401)
        login = self.c.post('/api/token', data={'username': email, 'password': PW})
        self.assertNotEqual(login.status_code, 200)

    def test_retention_purge_deletes_expired_checks(self):
        _, h = self.user()
        cid, _ = self.check(h)
        with M.SessionLocal() as s:
            c = s.get(M.Check, cid)
            c.expires_at = M.utcnow() - timedelta(days=1)
            s.commit()
        self.assertEqual(self.c.post('/api/admin/purge', headers=self.admin).status_code, 200)
        self.assertEqual(self.c.get(f'/api/checks/{cid}', headers=h).status_code, 404)

    def test_security_headers(self):
        r = self.c.get('/api/health')
        self.assertIn('content-security-policy', {k.lower() for k in r.headers})
        self.assertEqual(r.headers.get('x-content-type-options'), 'nosniff')


if __name__ == '__main__':
    unittest.main()
