"""Post-deploy smoke test: python scripts/smoke_test.py https://your-url"""

import json
import sys
import urllib.request


def main():
    base = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "http://127.0.0.1:8000"
    ).rstrip("/")

    def get(path):
        with urllib.request.urlopen(base + path, timeout=20) as r:
            return r.status, r.read(), dict(r.headers)

    status, body, _ = get("/api/health")
    assert status == 200, f"health check failed: {status}"

    status, body, _ = get("/api/health/ready")
    assert status == 200, f"readiness check failed: {status}"

    status, body, _ = get("/api/templates")
    templates = json.loads(body)
    assert len(templates) > 0, "No templates returned"

    status, body, headers = get("/")
    assert status == 200
    assert b"FundingLens Check" in body

    assert (
        "Content-Security-Policy" in headers
        or "content-security-policy" in headers
    )

    print("smoke test passed:", base)


if __name__ == "__main__":
    main()
