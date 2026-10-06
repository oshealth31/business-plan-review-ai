"""FundingLens Check - applicant-facing readiness check (separate product, separate database).

Applicants upload a business plan, get a free quick scan (counts only), and can unlock a full readiness report
against a generic sector template for credits. Funders never see this data.

The version lives in the VERSION file. Shared analysis lives in fundinglens_core (unit-tested without this stack).
"""
import hashlib
import hmac
import base64
import json
import logging
import os
import secrets
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
                        create_engine, delete, func, select, text as sqltext)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from fundinglens_core import analysis as A
from fundinglens_core import readiness as R
from fundinglens_core import templates as T
from fundinglens_core.ai import APPLICANT_INSTRUCTIONS as AP_INSTRUCTIONS, ai_commentary
from fundinglens_core.documents import DocumentError, extract_text, validate_upload
from . import billing as B
from .report_html import render_report_html

log = logging.getLogger('fundinglens.check')

# ----------------------------------------------------------------------------
# Configuration (fail closed in production)
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text().strip()
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production').lower()
IS_PROD = ENVIRONMENT == 'production'
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
DOCS = DATA / 'documents'
DOCS.mkdir(parents=True, exist_ok=True)
ALGORITHM = 'HS256'


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


MAX_UPLOAD_BYTES = _env_int('MAX_UPLOAD_BYTES', 10_000_000)
ACCESS_MINUTES = _env_int('ACCESS_TOKEN_MINUTES', 120)
CURRENCY = os.getenv('CURRENCY', 'BWP')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', '')
TERMS_VERSION = os.getenv('TERMS_VERSION', 'draft-2026-10')
REQUIRE_INVITE = _env_bool('REQUIRE_INVITE', True)
SIGNUP_FREE_CREDITS = _env_int('SIGNUP_FREE_CREDITS', 0)       # only used when REQUIRE_INVITE is false
RETENTION_DAYS = _env_int('RETENTION_DAYS', 30)
PRICING = B.Pricing(full=_env_int('FULL_REPORT_CREDITS', 2), recheck=_env_int('RECHECK_CREDITS', 1),
                    window_days=_env_int('RECHECK_WINDOW_DAYS', 30))
QUICK_PER_DAY = _env_int('QUICK_SCANS_PER_DAY', 10)
FULL_PER_DAY = _env_int('FULL_REPORTS_PER_DAY', 10)
AI_GLOBAL_PER_DAY = _env_int('AI_GLOBAL_DAILY_LIMIT', 300)
PURGE_INTERVAL_SECONDS = _env_int('PURGE_INTERVAL_SECONDS', 6 * 3600)
LOGIN_LIMIT = _env_int('LOGIN_LIMIT', 8)
LOGIN_IP_LIMIT = _env_int('LOGIN_IP_LIMIT', 40)
WEBHOOK_SECRET = os.getenv('PAYMENT_WEBHOOK_SECRET', '')
try:
    PACKS = B.parse_packs(os.getenv('PACKS_JSON', ''))
except ValueError as exc:
    raise RuntimeError(f'PACKS_JSON is invalid: {exc}')


def _database_url() -> str:
    url = os.getenv('DATABASE_URL', f"sqlite:///{DATA / 'check.db'}")
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg://' + url[len(prefix):]
    return url


DB_URL = _database_url()
IS_SQLITE = DB_URL.startswith('sqlite')

SECRET_KEY = os.getenv('JWT_SECRET', '')
if len(SECRET_KEY) < 32:
    if IS_PROD:
        raise RuntimeError('JWT_SECRET must be set to a random value of at least 32 characters in production.')
    SECRET_KEY = secrets.token_urlsafe(48)

ADMIN_EMAIL = B.normalise_email(os.getenv('ADMIN_EMAIL', ''))
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
if IS_PROD and (not B.valid_email(ADMIN_EMAIL) or len(ADMIN_PASSWORD) < 12):
    raise RuntimeError('ADMIN_EMAIL (valid) and ADMIN_PASSWORD (12+ characters) must be set in production.')
if not IS_PROD and not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(14)
    ADMIN_EMAIL = ADMIN_EMAIL or 'admin@example.com'
    log.warning('Development admin: %s / %s', ADMIN_EMAIL, ADMIN_PASSWORD)

ALLOWED_ORIGINS = [x.strip() for x in os.getenv('ALLOWED_ORIGINS', '').split(',') if x.strip()]
if '*' in ALLOWED_ORIGINS and IS_PROD:
    raise RuntimeError('ALLOWED_ORIGINS must not contain * in production.')

engine = create_engine(DB_URL, connect_args={'check_same_thread': False} if IS_SQLITE else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Money = Numeric(18, 2, asdecimal=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.isoformat() + 'Z' if dt else None


def new_id() -> str:
    return str(uuid.uuid4())


def ai_configured() -> bool:
    return bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL'))


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    terms_version: Mapped[str] = mapped_column(String(40), default='')
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Invite(Base):
    __tablename__ = 'invites'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LedgerEntry(Base):
    """Append-only. Balance = SUM(delta). `ref` is unique, which makes every grant/charge/purchase idempotent."""
    __tablename__ = 'credit_ledger'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Check(Base):
    __tablename__ = 'checks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    template_id: Mapped[str] = mapped_column(String(60))
    funding_request: Mapped[float] = mapped_column(Money, default=0)
    owner_contribution: Mapped[float] = mapped_column(Money, default=0)
    revenue_override: Mapped[float | None] = mapped_column(Money, nullable=True)
    expenses_override: Mapped[float | None] = mapped_column(Money, nullable=True)
    doc_name: Mapped[str] = mapped_column(String(255), default='')
    doc_storage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doc_sha256: Mapped[str] = mapped_column(String(64), default='')
    doc_size: Mapped[int] = mapped_column(Integer, default=0)
    last_band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    full_runs: Mapped[int] = mapped_column(Integer, default=0)
    last_full_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Run(Base):
    __tablename__ = 'runs'
    __table_args__ = (UniqueConstraint('check_id', 'number', name='uq_run_number'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    check_id: Mapped[str] = mapped_column(ForeignKey('checks.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10))  # quick | figures | full
    band: Mapped[str] = mapped_column(String(20), default='')
    credits_charged: Mapped[int] = mapped_column(Integer, default=0)
    ai_mode: Mapped[str] = mapped_column(String(20), default='rules_only')
    ai_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    idem_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PaymentEvent(Base):
    __tablename__ = 'payment_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True)
    email: Mapped[str] = mapped_column(String(254))
    credits: Mapped[int] = mapped_column(Integer)
    amount: Mapped[str] = mapped_column(String(40), default='')
    currency: Mapped[str] = mapped_column(String(8), default='')
    status: Mapped[str] = mapped_column(String(20))  # applied | unmatched
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def init_db():
    Base.metadata.create_all(engine)


# ----------------------------------------------------------------------------
# Security helpers
# ----------------------------------------------------------------------------
oauth2 = OAuth2PasswordBearer(tokenUrl='/api/token')
_RATE: dict[str, list[float]] = {}


def rate_ok(key: str, limit: int, window: int) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    if len(_RATE) > 5000:
        for k in [k for k, v in _RATE.items() if not v or now - v[-1] > window]:
            _RATE.pop(k, None)
    bucket = _RATE.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000)
    return 'pbkdf2_sha256$310000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_b, hash_b = stored.split('$', 3)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt_b), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(hash_b))
    except Exception:
        return False


def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def token_for(u: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(u.id), 'tv': u.token_version, 'iat': now,
                       'exp': now + timedelta(minutes=ACCESS_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2), s: Session = Depends(db)) -> User:
    try:
        p = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(p['sub'])
    except Exception:
        raise HTTPException(401, 'Invalid or expired token')
    u = s.get(User, uid)
    if not u or not u.active or u.deleted_at or p.get('tv') != u.token_version:
        raise HTTPException(401, 'Session is no longer valid')
    return u


def require_admin(u: User = Depends(current_user)) -> User:
    if not u.is_admin:
        raise HTTPException(403, 'Administrators only')
    return u


def client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


def credit_balance(s: Session, user_id: int) -> int:
    return int(s.scalar(select(func.coalesce(func.sum(LedgerEntry.delta), 0)).where(LedgerEntry.user_id == user_id)) or 0)


def ledger(s: Session, user_id: int, delta: int, reason: str, ref: str | None = None, note: str = '') -> LedgerEntry:
    e = LedgerEntry(user_id=user_id, delta=delta, reason=reason, ref=ref, note=note[:300])
    s.add(e)
    return e


# ----------------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------------
def amount():
    return Field(default=0.0, ge=0, le=1e12, allow_inf_nan=False)


class SignupRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    invite_code: str | None = Field(default=None, max_length=40)
    accept_terms: bool = False


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class DeleteAccount(BaseModel):
    password: str = Field(max_length=200)


class CheckCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    template_id: str = Field(max_length=60)
    funding_request: float = amount()
    owner_contribution: float = amount()


class FullRequest(BaseModel):
    use_ai: bool = False  # explicit per-report consent to send a redacted copy of the plan text to the AI provider


class FiguresRequest(BaseModel):
    revenue: float | None = Field(default=None, ge=0, le=1e13, allow_inf_nan=False)
    expenses: float | None = Field(default=None, ge=0, le=1e13, allow_inf_nan=False)


class InviteCreate(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    credits: int = Field(default=0, ge=0, le=1000)
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_days: int | None = Field(default=30, ge=1, le=365)
    note: str = Field(default='', max_length=200)


class CreditAdjust(BaseModel):
    email: str = Field(max_length=254)
    credits: int = Field(ge=-1000, le=1000)
    reason: str = Field(min_length=3, max_length=200)


class AdminPassword(BaseModel):
    password: str = Field(max_length=200)


class AdminActive(BaseModel):
    active: bool


# ----------------------------------------------------------------------------
# Checks: helpers
# ----------------------------------------------------------------------------
def get_check_or_404(s: Session, check_id: str, u: User) -> Check:
    c = s.get(Check, check_id)
    if not c or c.user_id != u.id:
        raise HTTPException(404, 'Check not found')
    return c


def template_or_500(c: Check) -> dict:
    t = T.get_template(c.template_id)
    if not t:
        raise HTTPException(500, 'This check uses a template that no longer exists.')
    return t


def next_run_number(s: Session, check_id: str) -> int:
    return int(s.scalar(select(func.coalesce(func.max(Run.number), 0)).where(Run.check_id == check_id)) or 0) + 1


def latest_run(s: Session, check_id: str, mode: str | None = None) -> Run | None:
    q = select(Run).where(Run.check_id == check_id)
    if mode:
        q = q.where(Run.mode == mode)
    return s.scalar(q.order_by(Run.number.desc()).limit(1))


def overrides_of(c: Check) -> dict:
    return {'revenue': c.revenue_override, 'expenses': c.expenses_override}


def unlink_doc(storage: str | None):
    if storage:
        try:
            (DOCS / storage).unlink()
        except FileNotFoundError:
            pass


def delete_check_rows(s: Session, c: Check):
    unlink_doc(c.doc_storage)
    s.execute(delete(Run).where(Run.check_id == c.id))
    s.delete(c)


def check_summary(c: Check) -> dict:
    return {'id': c.id, 'title': c.title, 'template_id': c.template_id,
            'template_name': (T.get_template(c.template_id) or {}).get('name', c.template_id),
            'has_document': bool(c.doc_storage), 'band': c.last_band, 'band_label': R.BANDS.get(c.last_band or '', ''),
            'full_runs': c.full_runs, 'created_at': iso(c.created_at), 'expires_at': iso(c.expires_at)}


def full_payload(s: Session, c: Check, run: Run, balance: int | None = None, charged: int | None = None, note: str = '') -> dict:
    result = json.loads(run.result_json)
    return {'report': R.applicant_report(result, template_or_500(c)),
            'run': {'number': run.number, 'created_at': iso(run.created_at), 'credits_charged': run.credits_charged},
            'stale': run.created_at < c.changed_at,
            'balance': credit_balance(s, c.user_id) if balance is None else balance,
            'charged': run.credits_charged if charged is None else charged, 'billing_note': note}


def check_detail(s: Session, c: Check, u: User) -> dict:
    t = template_or_500(c)
    last = latest_run(s, c.id)
    full = latest_run(s, c.id, 'full')
    runs = s.scalars(select(Run).where(Run.check_id == c.id).order_by(Run.number.desc()).limit(30)).all()
    now = utcnow()
    price = B.price_for_full(PRICING, c.last_full_at, now)
    return {
        **check_summary(c), 'template': T.public_view(t),
        'funding_request': c.funding_request, 'owner_contribution': c.owner_contribution,
        'overrides': overrides_of(c),
        'document': ({'name': c.doc_name, 'size_bytes': c.doc_size, 'sha256': c.doc_sha256} if c.doc_storage else None),
        'quick': R.quick_scan(json.loads(last.result_json)) if last else None,
        'full': full_payload(s, c, full) if full else None,
        'runs': [{'number': r.number, 'mode': r.mode, 'band': r.band, 'credits_charged': r.credits_charged,
                  'created_at': iso(r.created_at)} for r in runs],
        'price': price, 'is_recheck': price == PRICING.recheck and c.last_full_at is not None and price != PRICING.full,
        'balance': credit_balance(s, u.id), 'ai_available': ai_configured(),
    }


def run_rules(c: Check, text: str) -> tuple[dict, dict]:
    t = template_or_500(c)
    det = A.analyse_document(text, c.funding_request, c.owner_contribution, T.criteria_for(t), overrides_of(c))
    return det, t


def read_stored_text(c: Check) -> str:
    if not c.doc_storage:
        raise HTTPException(409, 'Upload your business plan first.')
    try:
        raw = (DOCS / c.doc_storage).read_bytes()
    except FileNotFoundError:
        raise HTTPException(410, 'Your uploaded plan is no longer stored. Please upload it again.')
    try:
        return extract_text(raw, Path(c.doc_storage).suffix.lower())
    except DocumentError as e:
        raise HTTPException(e.status, e.message)


def record_run(s: Session, c: Check, u: User, mode: str, result: dict, ai_meta: dict, *, charged: int = 0,
               idem_key: str | None = None) -> Run:
    band = R.quick_scan(result)['band']
    run = Run(id=new_id(), check_id=c.id, user_id=u.id, number=next_run_number(s, c.id), mode=mode, band=band,
              credits_charged=charged, ai_mode=ai_meta.get('mode', 'rules_only'), ai_model=ai_meta.get('model'),
              idem_key=idem_key, result_json=json.dumps(result))
    s.add(run)
    c.last_band = band
    c.expires_at = B.retention_deadline(utcnow(), RETENTION_DAYS)
    return run


# ----------------------------------------------------------------------------
# Retention and deletion
# ----------------------------------------------------------------------------
def purge_expired(s: Session) -> dict:
    expired = s.scalars(select(Check).where(Check.expires_at < utcnow())).all()
    for c in expired:
        delete_check_rows(s, c)
    s.commit()
    return {'checks_deleted': len(expired)}


def delete_user_data(s: Session, u: User):
    for c in s.scalars(select(Check).where(Check.user_id == u.id)).all():
        delete_check_rows(s, c)
    u.email = f'deleted-{u.id}@deleted.invalid'
    u.password_hash = '!'
    u.active, u.is_admin, u.deleted_at = False, False, utcnow()
    u.token_version += 1


_stop = threading.Event()


def _purge_loop():
    while not _stop.wait(PURGE_INTERVAL_SECONDS):
        try:
            with SessionLocal() as s:
                purge_expired(s)
        except Exception:
            log.exception('retention purge failed')


# ----------------------------------------------------------------------------
# Seed and lifecycle
# ----------------------------------------------------------------------------
def seed():
    s = SessionLocal()
    try:
        if ADMIN_EMAIL and not s.scalar(select(User).where(User.email == ADMIN_EMAIL)):
            s.add(User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), is_admin=True,
                       terms_version=TERMS_VERSION, terms_accepted_at=utcnow()))
            s.commit()
        if _env_bool('SEED_DEMO', False):
            pw = os.getenv('DEMO_PASSWORD', '')
            email = B.normalise_email(os.getenv('DEMO_EMAIL', 'demo@example.com'))
            if len(pw) < 12:
                log.warning('SEED_DEMO is set but DEMO_PASSWORD is missing or shorter than 12 characters.')
            elif not s.scalar(select(User).where(User.email == email)):
                u = User(email=email, password_hash=hash_password(pw), terms_version=TERMS_VERSION, terms_accepted_at=utcnow())
                s.add(u)
                s.flush()
                ledger(s, u.id, _env_int('DEMO_CREDITS', 10), 'grant_demo', ref=f'demo:{u.id}', note='Demo credits')
                s.commit()
    finally:
        s.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed()
    with SessionLocal() as s:
        purge_expired(s)
    t = None
    if PURGE_INTERVAL_SECONDS > 0:
        _stop.clear()
        t = threading.Thread(target=_purge_loop, daemon=True)
        t.start()
    yield
    _stop.set()


app = FastAPI(title='FundingLens Check', version=VERSION, lifespan=lifespan)
if ALLOWED_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                       allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'], allow_credentials=False)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware('http')
async def security_middleware(request: Request, call_next):
    cl = request.headers.get('content-length')
    if cl and cl.isdigit() and int(cl) > MAX_UPLOAD_BYTES + 1_000_000:
        return JSONResponse({'detail': 'Request body too large.'}, status_code=413)
    response = await call_next(request)
    h = response.headers
    h['X-Content-Type-Options'] = 'nosniff'
    h['X-Frame-Options'] = 'DENY'
    h['Referrer-Policy'] = 'no-referrer'
    h['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    h['Content-Security-Policy'] = CSP
    if IS_PROD:
        h['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    if request.url.path.startswith('/api/'):
        h['Cache-Control'] = 'no-store'
    return response


# ----------------------------------------------------------------------------
# Public endpoints
# ----------------------------------------------------------------------------
@app.get('/api/health')
def health():
    return {'status': 'ok', 'service': 'FundingLens Check', 'version': VERSION}


@app.get('/api/health/ready')
def readiness(s: Session = Depends(db)):
    checks = {'database': False, 'storage': DOCS.exists()}
    try:
        s.execute(sqltext('SELECT 1'))
        checks['database'] = True
    except Exception:
        pass
    ok = all(checks.values())
    return JSONResponse({'status': 'ready' if ok else 'degraded', 'version': VERSION, 'checks': checks},
                        status_code=200 if ok else 503)


@app.get('/api/config')
def public_config():
    return {'version': VERSION, 'currency': CURRENCY, 'require_invite': REQUIRE_INVITE,
            'pricing': {'full': PRICING.full, 'recheck': PRICING.recheck, 'window_days': PRICING.window_days},
            'retention_days': RETENTION_DAYS, 'terms_version': TERMS_VERSION, 'support_email': SUPPORT_EMAIL,
            'packs': PACKS, 'ai_available': ai_configured(), 'max_upload_bytes': MAX_UPLOAD_BYTES,
            'quick_scans_per_day': QUICK_PER_DAY}


@app.get('/api/templates')
def list_templates():
    return T.list_public()


# ----------------------------------------------------------------------------
# Accounts
# ----------------------------------------------------------------------------
@app.post('/api/auth/signup')
def signup(req: SignupRequest, request: Request, s: Session = Depends(db)):
    if not rate_ok(f'signup:{client_ip(request)}', 10, 3600):
        raise HTTPException(429, 'Too many sign-up attempts; try again later.')
    if not req.accept_terms:
        raise HTTPException(400, 'You must accept the terms and privacy notice to create an account.')
    email = B.normalise_email(req.email)
    if not B.valid_email(email):
        raise HTTPException(400, 'Please enter a valid email address.')
    problem = B.password_problem(req.password, email)
    if problem:
        raise HTTPException(400, problem)
    inv = None
    if REQUIRE_INVITE:
        code = B.normalise_invite_code(req.invite_code)
        inv = s.scalar(select(Invite).where(Invite.code == code).with_for_update()) if code else None
        if (not inv or not inv.active or inv.uses >= inv.max_uses or (inv.expires_at and inv.expires_at < utcnow())):
            raise HTTPException(400, 'That invite code is not valid or has expired.')
        if inv.email and inv.email != email:
            raise HTTPException(400, 'That invite was issued to a different email address.')
    if s.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'An account with this email already exists.')
    u = User(email=email, password_hash=hash_password(req.password), terms_version=TERMS_VERSION, terms_accepted_at=utcnow())
    s.add(u)
    try:
        s.flush()
    except IntegrityError:
        s.rollback()
        raise HTTPException(409, 'An account with this email already exists.')
    if inv:
        inv.uses += 1
        if inv.credits:
            ledger(s, u.id, inv.credits, 'grant_invite', ref=f'invite:{inv.id}:{u.id}', note=f'Invite {inv.code}')
    elif SIGNUP_FREE_CREDITS:
        ledger(s, u.id, SIGNUP_FREE_CREDITS, 'grant_signup', ref=f'signup:{u.id}')
    s.commit()
    return {'access_token': token_for(u), 'token_type': 'bearer', 'is_admin': u.is_admin}


@app.post('/api/token')
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), s: Session = Depends(db)):
    ip, email = client_ip(request), B.normalise_email(form.username)
    if not rate_ok(f'login:{ip}:{email}', LOGIN_LIMIT, 300) or not rate_ok(f'loginip:{ip}', LOGIN_IP_LIMIT, 300):
        raise HTTPException(429, 'Too many login attempts; try again later.')
    u = s.scalar(select(User).where(User.email == email))
    if not u or not u.active or u.deleted_at or not verify_password(form.password, u.password_hash):
        raise HTTPException(401, 'Incorrect email or password')
    u.last_login_at = utcnow()
    s.commit()
    return {'access_token': token_for(u), 'token_type': 'bearer', 'is_admin': u.is_admin}


@app.get('/api/me')
def me(u: User = Depends(current_user), s: Session = Depends(db)):
    return {'id': u.id, 'email': u.email, 'is_admin': u.is_admin, 'credits': credit_balance(s, u.id),
            'terms_version': u.terms_version}


@app.post('/api/me/password')
def change_password(req: PasswordChange, u: User = Depends(current_user), s: Session = Depends(db)):
    if not verify_password(req.current_password, u.password_hash):
        raise HTTPException(400, 'Current password is incorrect.')
    problem = B.password_problem(req.new_password, u.email)
    if problem:
        raise HTTPException(400, problem)
    u.password_hash = hash_password(req.new_password)
    u.token_version += 1
    s.commit()
    return {'status': 'changed', 'access_token': token_for(u)}


@app.post('/api/me/delete')
def delete_account(req: DeleteAccount, u: User = Depends(current_user), s: Session = Depends(db)):
    """Erase the user's plans, reports and personal details. Anonymised ledger rows are kept as financial records."""
    if not verify_password(req.password, u.password_hash):
        raise HTTPException(400, 'Password is incorrect.')
    delete_user_data(s, u)
    s.commit()
    return {'status': 'deleted'}


@app.get('/api/credits')
def credits(u: User = Depends(current_user), s: Session = Depends(db)):
    rows = s.scalars(select(LedgerEntry).where(LedgerEntry.user_id == u.id).order_by(LedgerEntry.id.desc()).limit(100)).all()
    return {'balance': credit_balance(s, u.id), 'packs': PACKS, 'currency': CURRENCY,
            'entries': [{'delta': e.delta, 'reason': e.reason, 'note': e.note, 'created_at': iso(e.created_at)} for e in rows]}


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------
@app.post('/api/checks')
def create_check(req: CheckCreate, u: User = Depends(current_user), s: Session = Depends(db)):
    if not T.get_template(req.template_id):
        raise HTTPException(422, 'Unknown template.')
    if s.scalar(select(func.count()).select_from(Check).where(Check.user_id == u.id)) >= 100:
        raise HTTPException(409, 'You have reached the limit of 100 saved checks. Delete some to continue.')
    now = utcnow()
    c = Check(id=new_id(), user_id=u.id, title=req.title.strip(), template_id=req.template_id,
              funding_request=req.funding_request, owner_contribution=req.owner_contribution,
              changed_at=now, expires_at=B.retention_deadline(now, RETENTION_DAYS))
    s.add(c)
    s.commit()
    return check_summary(c)


@app.get('/api/checks')
def list_checks(u: User = Depends(current_user), s: Session = Depends(db)):
    rows = s.scalars(select(Check).where(Check.user_id == u.id).order_by(Check.created_at.desc()).limit(100)).all()
    return [check_summary(c) for c in rows]


@app.get('/api/checks/{check_id}')
def get_check(check_id: str, u: User = Depends(current_user), s: Session = Depends(db)):
    return check_detail(s, get_check_or_404(s, check_id, u), u)


@app.delete('/api/checks/{check_id}')
def delete_check(check_id: str, u: User = Depends(current_user), s: Session = Depends(db)):
    c = get_check_or_404(s, check_id, u)
    delete_check_rows(s, c)
    s.commit()
    return {'status': 'deleted'}


@app.post('/api/checks/{check_id}/document')
def upload_document(check_id: str, file: UploadFile = File(...), u: User = Depends(current_user), s: Session = Depends(db)):
    """Store the plan and run the FREE quick scan (counts only). Plain `def`: runs in a worker thread."""
    c = get_check_or_404(s, check_id, u)
    since = utcnow() - timedelta(hours=24)
    used = s.scalar(select(func.count()).select_from(Run).where(Run.user_id == u.id, Run.mode == 'quick', Run.created_at >= since))
    if used >= QUICK_PER_DAY:
        raise HTTPException(429, f'You have used your {QUICK_PER_DAY} free quick scans for today. Try again tomorrow.')
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f'File exceeds the maximum upload size of {MAX_UPLOAD_BYTES // 1_000_000} MB.')
    suffix = Path(file.filename or '').suffix.lower()
    try:
        text = extract_text(data, suffix)
    except DocumentError as e:
        raise HTTPException(e.status, e.message)
    stored = f'{c.id}_{uuid.uuid4().hex}{suffix}'
    (DOCS / stored).write_bytes(data)
    old = c.doc_storage
    try:
        had_overrides = c.revenue_override is not None or c.expenses_override is not None
        c.revenue_override = c.expenses_override = None  # a new document usually changes the figures
        c.doc_name, c.doc_storage, c.doc_size = (file.filename or stored)[:255], stored, len(data)
        c.doc_sha256 = hashlib.sha256(data).hexdigest()
        c.changed_at = utcnow()
        det, _ = run_rules(c, text)
        result = A.build_result(det, None, {'mode': 'rules_only', 'message': 'Quick scan: checklist rules only.'})
        record_run(s, c, u, 'quick', result, {'mode': 'rules_only'})
        s.commit()
    except Exception:
        s.rollback()
        unlink_doc(stored)
        raise
    unlink_doc(old)
    return {'quick': R.quick_scan(result), 'figures_reset': had_overrides, 'document': {'name': c.doc_name, 'size_bytes': c.doc_size}}


@app.post('/api/checks/{check_id}/figures')
def set_figures(check_id: str, req: FiguresRequest, u: User = Depends(current_user), s: Session = Depends(db)):
    """Confirm or correct revenue/expenses. Free: re-runs the rules only (no AI, no charge)."""
    c = get_check_or_404(s, check_id, u)
    text = read_stored_text(c)
    c.revenue_override, c.expenses_override = req.revenue, req.expenses
    c.changed_at = utcnow()
    det, _ = run_rules(c, text)
    result = A.build_result(det, None, {'mode': 'rules_only', 'message': 'Figures updated: checklist rules only.'})
    record_run(s, c, u, 'figures', result, {'mode': 'rules_only'})
    s.commit()
    return {'quick': R.quick_scan(result)}


def _full_response(s: Session, c: Check, run: Run, note: str = '') -> dict:
    return full_payload(s, c, run, note=note)


@app.post('/api/checks/{check_id}/full')
def unlock_full_report(check_id: str, body: FullRequest | None = None, idempotency_key: str | None = Header(default=None),
                       u: User = Depends(current_user), s: Session = Depends(db)):
    """Create the full readiness report (rules + optional AI commentary). Costs credits. Plain `def`: worker thread."""
    c = get_check_or_404(s, check_id, u)
    ikey = None
    if idempotency_key:
        if not 8 <= len(idempotency_key) <= 80 or not all(ch.isalnum() or ch in '-_' for ch in idempotency_key):
            raise HTTPException(400, 'Invalid Idempotency-Key.')
        ikey = f'{u.id}:{c.id}:{idempotency_key}'
        prior = s.scalar(select(Run).where(Run.idem_key == ikey))
        if prior:
            return _full_response(s, c, prior, 'This request was already processed; no additional credits were charged.')
    now = utcnow()
    since = now - timedelta(hours=24)
    if s.scalar(select(func.count()).select_from(Run).where(Run.user_id == u.id, Run.mode == 'full', Run.created_at >= since)) >= FULL_PER_DAY:
        raise HTTPException(429, f'Daily limit of {FULL_PER_DAY} full reports reached. Try again tomorrow.')
    price = B.price_for_full(PRICING, c.last_full_at, now)
    balance = credit_balance(s, u.id)
    if balance < price:
        return JSONResponse(status_code=402, content={'detail': f'This report costs {price} credit(s) and you have {balance}.',
                                                      'needed': price, 'balance': balance})
    text = read_stored_text(c)
    det, _ = run_rules(c, text)
    ai_out, ai_meta, note = None, {'mode': 'rules_only', 'message': 'Checklist rules only (you did not ask for AI commentary, or it is not enabled).'}, ''
    charge = price
    want_ai = bool(body and body.use_ai)
    if want_ai and ai_configured():
        today_ai = s.scalar(select(func.count()).select_from(Run).where(Run.ai_mode == 'llm', Run.created_at >= since))
        if today_ai >= AI_GLOBAL_PER_DAY:
            ai_meta = {'mode': 'rules_only', 'message': 'AI commentary is temporarily unavailable (daily capacity reached).'}
            charge, note = 0, 'AI commentary was unavailable, so you were not charged. Try again later for the AI notes.'
        else:
            t = template_or_500(c)
            ai_out, ai_meta, _ = ai_commentary(
                api_key=os.getenv('OPENAI_API_KEY'), model=os.getenv('OPENAI_MODEL'),
                timeout=float(os.getenv('OPENAI_TIMEOUT', '45')), text=text, applicant='Applicant', det=det,
                criteria=T.criteria_for(t), instructions=AP_INSTRUCTIONS)
            if ai_meta.get('mode') != 'llm':
                charge, note = 0, 'AI commentary was unavailable, so you were not charged. Try again later for the AI notes.'
    result = A.build_result(det, ai_out, ai_meta)
    # Charge and record atomically: lock the user row, re-check the balance, then write both.
    s.scalar(select(User.id).where(User.id == u.id).with_for_update())
    if charge and credit_balance(s, u.id) < charge:
        return JSONResponse(status_code=402, content={'detail': 'Not enough credits.', 'needed': charge,
                                                      'balance': credit_balance(s, u.id)})
    try:
        run = record_run(s, c, u, 'full', result, ai_meta, charged=charge, idem_key=ikey)
        s.flush()
        if charge:
            ledger(s, u.id, -charge, 'charge_recheck' if charge == PRICING.recheck and c.last_full_at else 'charge_full',
                   ref=f'run:{run.id}', note=c.title[:100])
            c.last_full_at = now
        c.full_runs += 1
        s.commit()
    except IntegrityError:
        s.rollback()
        prior = s.scalar(select(Run).where(Run.idem_key == ikey)) if ikey else None
        if prior:
            return _full_response(s, c, prior, 'This request was already processed; no additional credits were charged.')
        raise HTTPException(409, 'Please try again.')
    return _full_response(s, c, run, note)


@app.get('/api/checks/{check_id}/runs/{number}')
def get_full_run(check_id: str, number: int, u: User = Depends(current_user), s: Session = Depends(db)):
    c = get_check_or_404(s, check_id, u)
    run = s.scalar(select(Run).where(Run.check_id == c.id, Run.number == number, Run.mode == 'full'))
    if not run:
        raise HTTPException(404, 'Report not found')
    return _full_response(s, c, run)


@app.get('/api/checks/{check_id}/report', response_class=HTMLResponse)
def printable_report(check_id: str, run: int | None = None, u: User = Depends(current_user), s: Session = Depends(db)):
    c = get_check_or_404(s, check_id, u)
    r = (s.scalar(select(Run).where(Run.check_id == c.id, Run.number == run, Run.mode == 'full')) if run
         else latest_run(s, c.id, 'full'))
    if not r:
        raise HTTPException(404, 'There is no full report yet.')
    report = R.applicant_report(json.loads(r.result_json), template_or_500(c))
    return HTMLResponse(render_report_html(c.title, report, generated=r.created_at.strftime('%Y-%m-%d %H:%M UTC'),
                                           version=VERSION, currency=CURRENCY))


# ----------------------------------------------------------------------------
# Payments (provider-neutral signed webhook)
# ----------------------------------------------------------------------------
@app.post('/api/payments/webhook')
async def payment_webhook(request: Request, s: Session = Depends(db)):
    body = await request.body()
    if len(body) > 20000:
        raise HTTPException(413, 'Body too large')
    ok, why = B.verify_webhook(WEBHOOK_SECRET, request.headers.get('x-fl-timestamp'), request.headers.get('x-fl-signature'), body)
    if not ok:
        log.warning('payment webhook rejected: %s', why)
        raise HTTPException(401, why)
    try:
        ev = B.parse_webhook_event(body)
    except ValueError as e:
        raise HTTPException(422, str(e))
    existing = s.scalar(select(PaymentEvent).where(PaymentEvent.event_id == ev['event_id']))
    if existing:
        return {'status': 'duplicate', 'result': existing.status}
    user = s.scalar(select(User).where(User.email == ev['email'], User.deleted_at.is_(None)))
    status = 'applied' if user else 'unmatched'
    s.add(PaymentEvent(event_id=ev['event_id'], email=ev['email'], credits=ev['credits'], amount=ev['amount'],
                       currency=ev['currency'], status=status))
    if user:
        ledger(s, user.id, ev['credits'], 'purchase', ref=f"purchase:{ev['event_id']}", note=f"{ev['amount']} {ev['currency']}".strip())
    else:
        log.error('payment %s for unknown email %s needs manual reconciliation', ev['event_id'], ev['email'])
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        return {'status': 'duplicate'}
    return {'status': status}


# ----------------------------------------------------------------------------
# Admin
# ----------------------------------------------------------------------------
def invite_dict(i: Invite) -> dict:
    return {'id': i.id, 'code': i.code, 'email': i.email, 'credits': i.credits, 'max_uses': i.max_uses, 'uses': i.uses,
            'expires_at': iso(i.expires_at), 'note': i.note, 'active': i.active, 'created_at': iso(i.created_at)}


@app.post('/api/admin/invites')
def create_invite(req: InviteCreate, u: User = Depends(require_admin), s: Session = Depends(db)):
    email = B.normalise_email(req.email) if req.email else None
    if email and not B.valid_email(email):
        raise HTTPException(422, 'Invalid email.')
    for _ in range(5):
        code = B.make_invite_code()
        if not s.scalar(select(Invite.id).where(Invite.code == code)):
            break
    inv = Invite(id=new_id(), code=code, email=email, credits=req.credits, max_uses=req.max_uses, note=req.note,
                 expires_at=utcnow() + timedelta(days=req.expires_days) if req.expires_days else None, created_by=u.id)
    s.add(inv)
    s.commit()
    return invite_dict(inv)


@app.get('/api/admin/invites')
def list_invites(u: User = Depends(require_admin), s: Session = Depends(db)):
    return [invite_dict(i) for i in s.scalars(select(Invite).order_by(Invite.created_at.desc()).limit(200)).all()]


@app.post('/api/admin/invites/{invite_id}/revoke')
def revoke_invite(invite_id: str, u: User = Depends(require_admin), s: Session = Depends(db)):
    inv = s.get(Invite, invite_id)
    if not inv:
        raise HTTPException(404, 'Invite not found')
    inv.active = False
    s.commit()
    return invite_dict(inv)


@app.post('/api/admin/credits')
def adjust_credits(req: CreditAdjust, u: User = Depends(require_admin), s: Session = Depends(db)):
    if req.credits == 0:
        raise HTTPException(422, 'credits must not be zero')
    target = s.scalar(select(User).where(User.email == B.normalise_email(req.email), User.deleted_at.is_(None)))
    if not target:
        raise HTTPException(404, 'No user with that email.')
    ledger(s, target.id, req.credits, 'admin_grant' if req.credits > 0 else 'admin_adjust', note=f'{req.reason} (by {u.email})')
    s.commit()
    return {'email': target.email, 'balance': credit_balance(s, target.id)}


@app.get('/api/admin/users')
def admin_users(u: User = Depends(require_admin), s: Session = Depends(db)):
    balances = dict(s.execute(select(LedgerEntry.user_id, func.sum(LedgerEntry.delta)).group_by(LedgerEntry.user_id)).all())
    checks = dict(s.execute(select(Check.user_id, func.count()).group_by(Check.user_id)).all())
    fulls = dict(s.execute(select(Run.user_id, func.count()).where(Run.mode == 'full').group_by(Run.user_id)).all())
    rows = s.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()).limit(500)).all()
    return [{'id': x.id, 'email': x.email, 'is_admin': x.is_admin, 'active': x.active, 'credits': int(balances.get(x.id, 0) or 0),
             'checks': checks.get(x.id, 0), 'full_reports': fulls.get(x.id, 0), 'created_at': iso(x.created_at),
             'last_login_at': iso(x.last_login_at)} for x in rows]


@app.post('/api/admin/users/{user_id}/password')
def admin_reset_password(user_id: int, req: AdminPassword, u: User = Depends(require_admin), s: Session = Depends(db)):
    x = s.get(User, user_id)
    if not x or x.deleted_at:
        raise HTTPException(404, 'User not found')
    problem = B.password_problem(req.password, x.email)
    if problem:
        raise HTTPException(400, problem)
    x.password_hash, x.token_version = hash_password(req.password), x.token_version + 1
    s.commit()
    return {'status': 'reset'}


@app.post('/api/admin/users/{user_id}/active')
def admin_set_active(user_id: int, req: AdminActive, u: User = Depends(require_admin), s: Session = Depends(db)):
    x = s.get(User, user_id)
    if not x or x.deleted_at:
        raise HTTPException(404, 'User not found')
    if x.id == u.id and not req.active:
        raise HTTPException(400, 'You cannot deactivate your own account.')
    x.active, x.token_version = req.active, x.token_version + 1
    s.commit()
    return {'id': x.id, 'active': x.active}


@app.get('/api/admin/usage')
def admin_usage(u: User = Depends(require_admin), s: Session = Depends(db)):
    now = utcnow()
    since = now - timedelta(days=14)
    runs = s.execute(select(Run.created_at, Run.mode, Run.ai_mode, Run.credits_charged).where(Run.created_at >= since)).all()
    per_day: dict[str, dict] = {}
    for created, mode, ai_mode, charged in runs:
        d = per_day.setdefault(created.strftime('%Y-%m-%d'), {'quick': 0, 'figures': 0, 'full': 0, 'ai': 0, 'credits': 0})
        d[mode] = d.get(mode, 0) + 1
        d['ai'] += 1 if ai_mode == 'llm' else 0
        d['credits'] += charged
    sums = dict(s.execute(select(LedgerEntry.reason, func.sum(LedgerEntry.delta)).group_by(LedgerEntry.reason)).all())
    return {
        'users': s.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None))),
        'active_7d': s.scalar(select(func.count()).select_from(User).where(User.last_login_at >= now - timedelta(days=7))),
        'checks': s.scalar(select(func.count()).select_from(Check)),
        'full_reports_total': s.scalar(select(func.count()).select_from(Run).where(Run.mode == 'full')),
        'ai_reports_total': s.scalar(select(func.count()).select_from(Run).where(Run.ai_mode == 'llm')),
        'credits_purchased': int(sums.get('purchase', 0) or 0),
        'credits_granted': int(sum(v or 0 for k, v in sums.items() if k.startswith('grant') or k == 'admin_grant')),
        'credits_spent': int(-sum(v or 0 for k, v in sums.items() if k.startswith('charge'))),
        'unmatched_payments': s.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.status == 'unmatched')),
        'per_day': dict(sorted(per_day.items())),
    }


@app.get('/api/admin/payments')
def admin_payments(u: User = Depends(require_admin), s: Session = Depends(db)):
    rows = s.scalars(select(PaymentEvent).order_by(PaymentEvent.id.desc()).limit(200)).all()
    return [{'event_id': p.event_id, 'email': p.email, 'credits': p.credits, 'amount': p.amount, 'currency': p.currency,
             'status': p.status, 'created_at': iso(p.created_at)} for p in rows]


@app.post('/api/admin/payments/{event_id}/resolve')
def admin_resolve_payment(event_id: str, u: User = Depends(require_admin), s: Session = Depends(db)):
    """Apply an unmatched payment once the buyer has an account (e.g. they paid with a different email and told you)."""
    p = s.scalar(select(PaymentEvent).where(PaymentEvent.event_id == event_id))
    if not p or p.status != 'unmatched':
        raise HTTPException(404, 'No unmatched payment with that id.')
    user = s.scalar(select(User).where(User.email == p.email, User.deleted_at.is_(None)))
    if not user:
        raise HTTPException(409, 'There is still no account with that email. Use Credits to grant to the right account instead.')
    ledger(s, user.id, p.credits, 'purchase', ref=f'purchase:{p.event_id}', note=f'{p.amount} {p.currency}'.strip())
    p.status = 'applied'
    s.commit()
    return {'status': 'applied'}


@app.post('/api/admin/purge')
def admin_purge(u: User = Depends(require_admin), s: Session = Depends(db)):
    return purge_expired(s)


# Static frontend is mounted last so /api/* routes take precedence.
app.mount('/', StaticFiles(directory=ROOT / 'frontend', html=True), name='frontend')
