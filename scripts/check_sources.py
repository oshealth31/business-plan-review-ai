"""Weekly check that the funder documents behind the published packs have not changed.

First run (or with --update) writes docs/sources.lock.json; later runs compare SHA-256 of each source and exit 1 on drift.
A drift means: a human must re-read the source and update fundinglens_core/published.py (and PACKS_VERSION).
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fundinglens_core.published import PUBLISHED_PACKS  # noqa: E402

LOCK = Path(__file__).resolve().parents[1] / 'docs' / 'sources.lock.json'
urls = sorted({s['url'] for p in PUBLISHED_PACKS for s in p['sources']})
now = {}
for u in urls:
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'FundingLensCheck-source-monitor'})
        now[u] = hashlib.sha256(urllib.request.urlopen(req, timeout=30).read()).hexdigest()
    except Exception as e:  # unreachable is reported, not hidden
        now[u] = f'ERROR {type(e).__name__}'
if '--update' in sys.argv or not LOCK.exists():
    LOCK.write_text(json.dumps(now, indent=2, sort_keys=True) + '\n'); print('baseline written'); sys.exit(0)
old = json.loads(LOCK.read_text()); bad = [u for u in urls if old.get(u) != now[u]]
for u in bad:
    print('CHANGED or unreachable:', u, old.get(u), '->', now[u])
sys.exit(1 if bad else 0)
