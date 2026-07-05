"""
SimpleFIN Bridge integration — claim setup tokens and fetch account data.
"""
import base64
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


class SimplefinError(Exception):
    pass


async def claim_access_url(setup_token: str) -> str:
    """Exchange a one-time setup token for a permanent access URL."""
    try:
        claim_url = base64.b64decode(setup_token.strip()).decode().strip()
    except Exception as exc:
        raise SimplefinError("Invalid SimpleFIN setup token encoding") from exc

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.post(claim_url, headers={"Content-Length": "0"})
        if resp.status_code >= 400:
            raise SimplefinError(f"Failed to claim token: HTTP {resp.status_code}")
        access_url = resp.text.strip()
        if not access_url.startswith("http"):
            raise SimplefinError("Claim response did not return a valid access URL")
        return access_url


async def fetch_accounts(
    access_url: str,
    start_date: int | None = None,
    end_date: int | None = None,
) -> dict:
    """
    Fetch all linked accounts and transactions from SimpleFIN.

    Note: SimpleFIN Bridge caps each request to a 90-day date range. Callers that
    need more history must issue multiple chunked requests (see sync_service).
    """
    base = access_url.rstrip("/") + "/"
    url = urljoin(base, "accounts")
    params: dict[str, str | int] = {"version": 2}
    if start_date is not None:
        params["start-date"] = start_date
    if end_date is not None:
        params["end-date"] = end_date

    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        resp = await client.get(url, params=params)
        if resp.status_code >= 400:
            raise SimplefinError(f"Failed to fetch accounts: HTTP {resp.status_code}")
        return resp.json()


def posted_to_date(posted: int | float | str) -> datetime:
    return datetime.fromtimestamp(int(posted), tz=timezone.utc)


def infer_account_type(name: str, org: str | None = None) -> tuple[str, str | None]:
    text = f"{name} {org or ''}".lower()
    if "credit" in text or "card" in text:
        return "credit", "credit card"
    if "savings" in text or "save" in text:
        return "depository", "savings"
    if "checking" in text or "check" in text:
        return "depository", "checking"
    if "invest" in text or "broker" in text:
        return "investment", "brokerage"
    if "loan" in text or "mortgage" in text:
        return "loan", "loan"
    return "other", None
