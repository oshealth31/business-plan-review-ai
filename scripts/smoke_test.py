"""Post-deploy smoke test: python scripts/smoke_test.py https://your-app.example.com"""
import json
import sys
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000').rstrip('/')


def get(path):
    with urllib.request.urlopen(base + path, timeout=20) as r:
        return r.status, r.read(), dict(r.headers)


s, body, _ = get('/api/health'); assert s == 200, 'health'
s, body, _ = get('/api/health/ready'); assert s == 200, f'ready: {body[:200]}'
s, body, _ = get('/api/templates'); t = json.loads(body); assert len(t) >= 7 and 'weight' not in body.decode(), 'templates'
s, body, h = get('/'); assert s == 200 and b'FundingLens Check' in body, 'frontend'
assert 'Content-Security-Policy' in h or 'content-security-policy' in {k.lower() for k in h}, 'csp'
print('smoke test passed:', base)
