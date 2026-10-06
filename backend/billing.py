"""Billing, credits, webhook-signature and account-hygiene helpers. Standard library only, so it is
unit-tested without the web stack (tests/test_billing.py)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional


@dataclass(frozen=True)
class Pricing:
    full: int = 2          # credits for the first full report on a check
    recheck: int = 1       # credits for another full report on the same check within the window
    window_days: int = 30


def price_for_full(p: Pricing, last_full_at: Optional[datetime], now: datetime) -> int:
    """First full report costs `full`; later ones on the same check within the window cost `recheck`."""
    if last_full_at is not None and now - last_full_at <= timedelta(days=p.window_days):
        return p.recheck
    return p.full


def balance(deltas: Iterable[int]) -> int:
    return int(sum(deltas))


# ---------------------------------------------------------------------------------------------
# Payment webhook: provider-neutral. Real providers (cards, mobile money, payment links) each sign
# differently; write a tiny adapter that verifies THEIR signature and forwards this event, or have
# the provider's server call this endpoint directly if it supports custom signing.
# ---------------------------------------------------------------------------------------------
WEBHOOK_TOLERANCE_SECONDS = 300


def sign_webhook(secret: str, timestamp, body: bytes) -> str:
    return hmac.new(secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256).hexdigest()


def verify_webhook(secret: str, timestamp, signature: Optional[str], body: bytes, *, now: Optional[float] = None,
                   tolerance: int = WEBHOOK_TOLERANCE_SECONDS) -> tuple[bool, str]:
    if not secret:
        return False, 'webhook is not configured'
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, 'bad timestamp'
    if abs((time.time() if now is None else now) - ts) > tolerance:
        return False, 'timestamp outside tolerance'
    if not hmac.compare_digest(sign_webhook(secret, ts, body), (signature or '').strip().lower()):
        return False, 'bad signature'
    return True, 'ok'


def parse_webhook_event(body: bytes) -> dict:
    """Validate the generic purchase event. Raises ValueError with a safe message."""
    try:
        d = json.loads(body)
    except Exception:
        raise ValueError('body is not valid JSON')
    if not isinstance(d, dict):
        raise ValueError('body must be an object')
    event_id = str(d.get('event_id', '')).strip()
    if not 3 <= len(event_id) <= 120:
        raise ValueError('event_id is required (3-120 characters)')
    if d.get('type') != 'credits.purchased':
        raise ValueError('unsupported event type')
    email = normalise_email(str(d.get('email', '')))
    if not valid_email(email):
        raise ValueError('a valid email is required')
    credits = d.get('credits')
    if not isinstance(credits, int) or isinstance(credits, bool) or not 1 <= credits <= 100000:
        raise ValueError('credits must be an integer between 1 and 100000')
    return {'event_id': event_id, 'email': email, 'credits': credits,
            'amount': str(d.get('amount', ''))[:40], 'currency': str(d.get('currency', ''))[:8]}


def parse_packs(raw: Optional[str]) -> list[dict]:
    """PACKS_JSON: [{"id","name","credits","price","currency","url"}]. `url` is where the buyer pays (payment link)."""
    if not raw or not raw.strip():
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError('PACKS_JSON must be a list')
    out = []
    for p in data:
        if not isinstance(p, dict):
            raise ValueError('each pack must be an object')
        pid = str(p.get('id', '')).strip()
        credits = p.get('credits')
        if not re.fullmatch(r'[a-z0-9_-]{2,40}', pid):
            raise ValueError(f'bad pack id {pid!r}')
        if not isinstance(credits, int) or isinstance(credits, bool) or credits < 1:
            raise ValueError(f'pack {pid}: credits must be a positive integer')
        url = str(p.get('url', '')).strip()
        if url and not url.startswith('https://'):
            raise ValueError(f'pack {pid}: url must start with https://')
        out.append({'id': pid, 'name': str(p.get('name', pid))[:80], 'credits': credits,
                    'price': str(p.get('price', ''))[:20], 'currency': str(p.get('currency', ''))[:8], 'url': url})
    return out


# ---------------------------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------------------------
_INVITE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'  # no 0/O/1/I/L


def make_invite_code() -> str:
    pick = lambda n: ''.join(secrets.choice(_INVITE_ALPHABET) for _ in range(n))  # noqa: E731
    return f'FL-{pick(4)}-{pick(4)}'


def normalise_invite_code(code: Optional[str]) -> str:
    return re.sub(r'\s+', '', (code or '')).upper()


def normalise_email(s: str) -> str:
    return (s or '').strip().lower()


def valid_email(s: str) -> bool:
    return len(s) <= 254 and re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', s) is not None


def password_problem(password: str, email: str = '') -> Optional[str]:
    if len(password) < 12:
        return 'Password must contain at least 12 characters.'
    if len(set(password)) < 5:
        return 'Password is too repetitive.'
    local = normalise_email(email).split('@')[0]
    if len(local) >= 4 and local in password.lower():
        return 'Password must not contain your email name.'
    return None


def retention_deadline(now: datetime, days: int) -> datetime:
    return now + timedelta(days=days)
