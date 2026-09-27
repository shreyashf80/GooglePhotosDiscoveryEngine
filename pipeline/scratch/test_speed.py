import requests
import time

routes = [
    "/api/v1/overview",
    "/api/v1/funnel",
    "/api/v1/hypotheses",
    "/api/v1/gap-matrix",
    "/api/v1/emergent-labels"
]
base_url = "http://127.0.0.1:8000"
headers = {"X-API-Key": "dev_key"}

for r in routes:
    start = time.time()
    res = requests.get(base_url + r, headers=headers)
    dur = time.time() - start
    print(f"{r}: {res.status_code} in {dur:.3f}s. Headers: {res.headers.get('X-Process-Time')}s, {res.headers.get('X-SQL-Queries')} queries.")

