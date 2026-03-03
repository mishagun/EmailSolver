#!/usr/bin/env python3
import subprocess
import sys
import webbrowser

import httpx

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def check(*, label: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return passed


def run_migrations() -> bool:
    print("[1/7] Running database migrations...")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Migration failed: {result.stderr.strip()}")
        return False
    print("  Migrations applied successfully")
    return True


def run() -> None:
    print("\n=== EmailSolver Auth Flow Test ===\n")

    # Step 1: Run migrations
    if not run_migrations():
        sys.exit(1)

    # Step 2: Health check
    print(f"\n[2/7] Checking server health...")
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
    except httpx.ConnectError:
        print("  Server not running. Start it with:")
        print("    uv run uvicorn app.main:app --reload")
        sys.exit(1)

    if not check(label="Health endpoint", passed=resp.status_code == 200, detail=resp.text):
        sys.exit(1)

    # Step 3: Get Google auth URL
    print("\n[3/7] Getting Google login URL...")
    resp = httpx.get(f"{API}/auth/login", follow_redirects=False, timeout=10)
    check(label="Login returns redirect", passed=resp.status_code == 307)

    auth_url = resp.headers.get("location", "")
    check(label="Redirect points to Google", passed="accounts.google.com" in auth_url)

    if "accounts.google.com" not in auth_url:
        print("  Check your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
        sys.exit(1)

    # Step 4: Unauthenticated access is blocked
    print("\n[4/7] Verifying unauthenticated access is rejected...")
    resp = httpx.get(f"{API}/auth/status", timeout=5)
    check(label="GET /auth/status without token", passed=resp.status_code in (401, 403))

    resp = httpx.get(f"{API}/emails", timeout=5)
    check(label="GET /emails without token", passed=resp.status_code in (401, 403))

    # Step 5: Browser login
    print("\n[5/7] Opening browser for Google sign-in...")
    print(f"  URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)
    print("\n  Complete the Google sign-in in your browser.")
    print('  The browser will show a JSON response like: {"access_token": "eyJ..."}\n')

    token = input("  Paste the access_token value here: ").strip().strip('"')

    if not token:
        print("  No token provided. Aborting.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # Step 6: Test authenticated endpoints
    print("\n[6/7] Testing authenticated endpoints...")

    resp = httpx.get(f"{API}/auth/status", headers=headers, timeout=10)
    status_ok = resp.status_code == 200
    check(label="GET /auth/status", passed=status_ok, detail=resp.text[:100])

    if status_ok:
        data = resp.json()
        check(label="Response has email", passed=bool(data.get("email")))
        check(label="authenticated=true", passed=data.get("authenticated") is True)

    resp = httpx.get(f"{API}/emails", headers=headers, params={"max_results": 3}, timeout=30)
    emails_ok = resp.status_code == 200
    check(label="GET /emails", passed=emails_ok, detail=f"status={resp.status_code}")

    if emails_ok:
        data = resp.json()
        check(label="Response has emails list", passed="emails" in data)
        check(label="Response has total count", passed="total" in data)
        print(f"  Fetched {data.get('total', '?')} emails")

    resp = httpx.get(f"{API}/emails/stats", headers=headers, timeout=30)
    stats_ok = resp.status_code == 200
    check(label="GET /emails/stats", passed=stats_ok, detail=f"status={resp.status_code}")

    if stats_ok:
        data = resp.json()
        print(f"  Unread: {data.get('unread_count', '?')}, Total: {data.get('total_count', '?')}")

    # Step 7: Logout
    print("\n[7/7] Testing logout...")
    resp = httpx.delete(f"{API}/auth/logout", headers=headers, timeout=10)
    check(label="DELETE /auth/logout", passed=resp.status_code == 200, detail=resp.text[:100])

    resp = httpx.get(f"{API}/auth/status", headers=headers, timeout=5)
    check(
        label="Token rejected after logout",
        passed=resp.status_code in (401, 403),
        detail=f"status={resp.status_code}",
    )

    print("\n=== Done ===\n")


if __name__ == "__main__":
    run()
