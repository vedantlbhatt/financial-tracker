#!/usr/bin/env python3
"""
Claim a SimpleFIN setup token and print the permanent access URL.

The access URL is NOT shown on simplefin.org. You only get it once, as the
raw response body from POSTing to the decoded claim URL.

Usage (from repo root):
  python backend/scripts/claim_simplefin.py

Then paste the printed line into .env:
  SIMPLEFIN_ACCESS_URL=<the full url>

You can comment out SIMPLEFIN_TOKEN after that — the token is one-time use.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def main() -> int:
    token = os.environ.get("SIMPLEFIN_TOKEN", "").strip()
    if not token:
        print("No SIMPLEFIN_TOKEN in .env", file=sys.stderr)
        print("Get one at https://beta-bridge.simplefin.org", file=sys.stderr)
        return 1

    try:
        claim_url = base64.b64decode(token).decode().strip()
    except Exception as exc:
        print(f"Invalid SIMPLEFIN_TOKEN (not valid base64): {exc}", file=sys.stderr)
        return 1

    print("Claim URL:", claim_url)
    print("Claiming (one-time only)...")

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        resp = client.post(claim_url, headers={"Content-Length": "0"})

    if resp.status_code != 200:
        print(f"Claim failed: HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        if resp.status_code == 403:
            print(
                "\nThis token was already used. Generate a NEW token at "
                "https://beta-bridge.simplefin.org and update SIMPLEFIN_TOKEN in .env.",
                file=sys.stderr,
            )
        return 1

    access_url = resp.text.strip()
    if not access_url.startswith("http"):
        print("Unexpected response (expected access URL):", resp.text, file=sys.stderr)
        return 1

    print("\n" + "=" * 72)
    print("SUCCESS — save this in .env as SIMPLEFIN_ACCESS_URL")
    print("=" * 72)
    print(f"\nSIMPLEFIN_ACCESS_URL={access_url}\n")
    print("=" * 72)
    print("Also fine: the app stores this encrypted in Postgres when you register")
    print("or click 'Connect' in Settings — you don't need .env if that worked.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
