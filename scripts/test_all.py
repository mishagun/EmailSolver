#!/usr/bin/env python3
import subprocess
import sys
import time
import webbrowser

from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"
TOTAL_STEPS = 11


def check(*, label: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return passed


def step(n: int, title: str) -> None:
    print(f"\n[{n}/{TOTAL_STEPS}] {title}")


def run() -> None:
    print("\n=== EmailSolver Comprehensive Test ===\n")

    headers: dict[str, str] = {}
    analysis_id: int | None = None

    # ── Step 1: Migrations ──
    step(1, "Running database migrations...")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if not check(label="Migrations", passed=result.returncode == 0, detail=result.stderr.strip()[:120]):
        sys.exit(1)

    # ── Step 2: Health check ──
    step(2, "Checking server health...")
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
    except httpx.ConnectError:
        print("  Server not running. Start it with:")
        print("    uv run uvicorn app.main:app --reload")
        sys.exit(1)
    if not check(label="GET /health", passed=resp.status_code == 200, detail=resp.text[:100]):
        sys.exit(1)

    # ── Step 3: Google auth URL ──
    step(3, "Getting Google login URL...")
    resp = httpx.get(f"{API}/auth/login", follow_redirects=False, timeout=10)
    check(label="Login returns 307", passed=resp.status_code == 307)
    auth_url = resp.headers.get("location", "")
    if not check(label="Redirect to Google", passed="accounts.google.com" in auth_url):
        print("  Check GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env")
        sys.exit(1)

    # ── Step 4: Unauthenticated access blocked ──
    step(4, "Verifying unauthenticated access is rejected...")
    for endpoint, method in [
        (f"{API}/auth/status", "GET"),
        (f"{API}/emails", "GET"),
        (f"{API}/analysis", "POST"),
    ]:
        if method == "GET":
            resp = httpx.get(endpoint, timeout=5)
        else:
            resp = httpx.post(endpoint, json={}, timeout=5)
        check(label=f"{method} {endpoint.replace(API, '')}", passed=resp.status_code in (401, 403))

    # ── Step 5: Browser OAuth login ──
    step(5, "Opening browser for Google sign-in...")
    print(f"  URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)
    print("\n  Complete Google sign-in in your browser.")
    print('  The browser will show JSON like: {"access_token": "eyJ..."}\n')
    token = input("  Paste the access_token value here: ").strip().strip('"')
    if not token:
        print("  No token provided. Aborting.")
        sys.exit(1)
    headers = {"Authorization": f"Bearer {token}"}

    # ── Step 6: Auth status ──
    step(6, "Checking auth status...")
    resp = httpx.get(f"{API}/auth/status", headers=headers, timeout=10)
    if check(label="GET /auth/status", passed=resp.status_code == 200, detail=resp.text[:100]):
        data = resp.json()
        check(label="authenticated=true", passed=data.get("authenticated") is True)
        check(label="email present", passed=bool(data.get("email")))

    # ── Step 7: Email listing + stats ──
    step(7, "Fetching emails and stats...")
    resp = httpx.get(f"{API}/emails", headers=headers, params={"max_results": 5}, timeout=30)
    if check(label="GET /emails", passed=resp.status_code == 200):
        data = resp.json()
        check(label="has emails list", passed="emails" in data)
        check(label="has total count", passed="total" in data)
        print(f"  Fetched {len(data.get('emails', []))} emails, total: {data.get('total', '?')}")

    resp = httpx.get(f"{API}/emails/stats", headers=headers, timeout=30)
    if check(label="GET /emails/stats", passed=resp.status_code == 200):
        data = resp.json()
        print(f"  Unread: {data.get('unread_count', '?')}, Total: {data.get('total_count', '?')}")

    # ── Step 8: Analysis lifecycle ──
    step(8, "Running analysis (max_emails=5)...")
    resp = httpx.post(
        f"{API}/analysis",
        headers=headers,
        json={"max_emails": 5},
        timeout=30,
    )
    if not check(label="POST /analysis → 202", passed=resp.status_code == 202):
        print(f"  Response: {resp.text[:200]}")
        _logout_and_exit(headers=headers)

    analysis_id = resp.json().get("id")
    print(f"  Analysis ID: {analysis_id}")

    # Poll until completed
    max_wait = 120
    interval = 3
    elapsed = 0
    final_status = "pending"

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        resp = httpx.get(f"{API}/analysis/{analysis_id}", headers=headers, timeout=10)
        if resp.status_code != 200:
            continue
        final_status = resp.json().get("status", "unknown")
        if final_status in ("completed", "failed"):
            break
        print(f"  ... status={final_status} ({elapsed}s)")

    if not check(label="Analysis completed", passed=final_status == "completed", detail=f"status={final_status}"):
        if final_status == "failed":
            print(f"  Error: {resp.json().get('error_message', 'unknown')}")
        _logout_and_exit(headers=headers)

    # Verify analysis response structure
    data = resp.json()
    check(label="has summary", passed=isinstance(data.get("summary"), list))
    classified = data.get("classified_emails", [])
    check(label="has classified_emails", passed=len(classified) > 0, detail=f"count={len(classified)}")

    if classified:
        email = classified[0]
        check(label="email has category", passed=bool(email.get("category")))
        check(label="email has importance", passed=bool(email.get("importance")))
        check(label="email has confidence", passed=email.get("confidence") is not None)

    # ── Step 9: Analysis list ──
    step(9, "Listing analyses...")
    resp = httpx.get(f"{API}/analysis", headers=headers, timeout=10)
    if check(label="GET /analysis", passed=resp.status_code == 200):
        analyses = resp.json().get("analyses", [])
        ids = [a["id"] for a in analyses]
        check(label="created analysis in list", passed=analysis_id in ids, detail=f"ids={ids}")

    # ── Step 10: Apply actions + error cases ──
    step(10, "Testing apply actions and error handling...")

    # 404 on non-existent analysis
    resp = httpx.get(f"{API}/analysis/999999", headers=headers, timeout=5)
    check(label="GET non-existent analysis → 404", passed=resp.status_code == 404)

    # move_to_category first (before mark_read, since action_taken blocks re-apply)
    categories = {e.get("category") for e in classified if e.get("category")}
    if categories:
        cat = next(iter(categories))
        resp = httpx.post(
            f"{API}/analysis/{analysis_id}/apply",
            headers=headers,
            json={"action": "move_to_category", "category": cat},
            timeout=30,
        )
        check(label=f"POST apply move_to_category ({cat}) → 200", passed=resp.status_code == 200, detail=resp.text[:100])
    else:
        print("  Skipping move_to_category — no categories found")

    # mark_read on remaining emails (ones not already acted on)
    resp = httpx.post(
        f"{API}/analysis/{analysis_id}/apply",
        headers=headers,
        json={"action": "mark_read"},
        timeout=30,
    )
    check(label="POST apply mark_read → 200", passed=resp.status_code == 200, detail=resp.text[:100])

    # ── Step 11: Delete + logout ──
    step(11, "Deleting analysis and logging out...")

    resp = httpx.delete(f"{API}/analysis/{analysis_id}", headers=headers, timeout=10)
    check(label="DELETE analysis → 200", passed=resp.status_code == 200)

    resp = httpx.get(f"{API}/analysis/{analysis_id}", headers=headers, timeout=5)
    check(label="GET deleted analysis → 404", passed=resp.status_code == 404)

    resp = httpx.delete(f"{API}/auth/logout", headers=headers, timeout=10)
    check(label="DELETE /auth/logout → 200", passed=resp.status_code == 200)

    resp = httpx.get(f"{API}/auth/status", headers=headers, timeout=5)
    check(label="Token rejected after logout", passed=resp.status_code in (401, 403))

    print("\n=== All tests complete ===\n")


def _logout_and_exit(*, headers: dict[str, str]) -> None:
    print("\n  Logging out before exit...")
    try:
        httpx.delete(f"{API}/auth/logout", headers=headers, timeout=10)
    except Exception:
        pass
    sys.exit(1)


if __name__ == "__main__":
    run()
