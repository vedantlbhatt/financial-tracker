"""
SimpleFIN sync service — poll /accounts and upsert local mirror.

SimpleFIN Bridge limits each GET /accounts request to a 90-day window. Initial
backfill walks backward in chunks; incremental syncs use a single recent window.
"""
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.account import Account
from app.models.simplefin_connection import SimplefinConnection
from app.models.transaction import Transaction
from app.services import category_service, simplefin_service
from app.services.crypto_service import decrypt_secret
from app.services.rollup_service import recompute_rollups_for_user
from app.services.simplefin_service import posted_to_date, infer_account_type

logger = logging.getLogger(__name__)
settings = get_settings()

BALANCE_FIELDS = ("name", "org", "balance", "currency", "balance-date", "available-balance", "available_balance")


async def _fetch_simplefin_data(
    access_url: str,
    *,
    full_backfill: bool,
    last_sync_at: datetime | None,
) -> tuple[dict, int]:
    """
    Fetch account + transaction data from SimpleFIN.
    Returns (merged_payload, api_calls_made).
    """
    now = int(time.time())

    # Incremental: one request covering roughly since last sync
    if not full_backfill and last_sync_at:
        start_ts = int(last_sync_at.timestamp()) - 86400
        data = await simplefin_service.fetch_accounts(access_url, start_date=start_ts)
        return data, 1

    # Initial / full backfill: 89-day chunks (Bridge max is 90 days per request)
    chunk_days = settings.simplefin_chunk_days
    max_chunks = settings.simplefin_max_backfill_chunks
    accounts_map: dict[str, dict] = {}
    all_errors: list = []
    api_calls = 0
    end_ts = now

    for chunk_idx in range(max_chunks):
        start_ts = end_ts - chunk_days * 86400
        chunk = await simplefin_service.fetch_accounts(
            access_url, start_date=start_ts, end_date=end_ts
        )
        api_calls += 1

        chunk_tx_count = 0
        for acct in chunk.get("accounts", []):
            aid = str(acct["id"])
            if aid not in accounts_map:
                accounts_map[aid] = {**acct, "transactions": [], "_tx_ids": set()}

            entry = accounts_map[aid]
            # Balances from the newest window only (first chunk)
            if chunk_idx == 0:
                for field in BALANCE_FIELDS:
                    if field in acct:
                        entry[field] = acct[field]

            for tx in acct.get("transactions") or []:
                tx_id = str(tx["id"])
                if tx_id not in entry["_tx_ids"]:
                    entry["_tx_ids"].add(tx_id)
                    entry["transactions"].append(tx)
                    chunk_tx_count += 1

        for err in chunk.get("errors") or chunk.get("errlist") or []:
            if err not in all_errors:
                all_errors.append(err)

        logger.info(
            "SimpleFIN chunk %s/%s (%s-day window): %s new txs",
            chunk_idx + 1,
            max_chunks,
            chunk_days,
            chunk_tx_count,
        )

        # No older transactions left (bank history exhausted)
        if chunk_tx_count == 0 and chunk_idx > 0:
            break

        end_ts = start_ts - 1
        if end_ts <= 0:
            break

    accounts = []
    for acct in accounts_map.values():
        acct.pop("_tx_ids", None)
        accounts.append(acct)

    return {"accounts": accounts, "errors": all_errors, "errlist": all_errors}, api_calls


async def _upsert_account(
    db: AsyncSession, connection: SimplefinConnection, acct: dict
) -> None:
    acct_type, subtype = infer_account_type(acct.get("name", ""), acct.get("org"))
    balance_date = None
    if acct.get("balance-date"):
        balance_date = posted_to_date(acct["balance-date"])

    balance = acct.get("balance")
    available = acct.get("available-balance", acct.get("available_balance"))
    external_id = str(acct["id"])
    sync_errors = acct.get("extra") if isinstance(acct.get("extra"), list) else None
    values = dict(
        name=acct.get("name", "Account"),
        institution_name=acct.get("org"),
        type=acct_type,
        subtype=subtype,
        current_balance=Decimal(str(balance)) if balance is not None else None,
        available_balance=Decimal(str(available)) if available is not None else None,
        balance_date=balance_date,
        iso_currency_code=acct.get("currency", "USD") or "USD",
        sync_errors=sync_errors,
    )

    # Reuse the same bank account if it was already imported under another connection.
    existing = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(
            SimplefinConnection.user_id == connection.user_id,
            Account.account_id == external_id,
        )
    )
    existing_id = existing.scalar_one_or_none()
    if existing_id:
        await db.execute(update(Account).where(Account.id == existing_id).values(**values))
        return

    stmt = (
        pg_insert(Account)
        .values(simplefin_connection_id=connection.id, account_id=external_id, **values)
        .on_conflict_do_update(
            constraint="uq_account_connection_external",
            set_=values,
        )
    )
    await db.execute(stmt)


async def _insert_transaction(
    db: AsyncSession, tx: dict, account_db_id, user_id: str
) -> bool:
    """Insert transaction if new. Returns True if inserted."""
    tx_external_id = str(tx["id"])
    existing = await db.execute(
        select(Transaction.id)
        .join(Account, Transaction.account_id == Account.id)
        .join(SimplefinConnection, Account.simplefin_connection_id == SimplefinConnection.id)
        .where(
            SimplefinConnection.user_id == user_id,
            Transaction.transaction_id == tx_external_id,
        )
    )
    if existing.scalar_one_or_none():
        return False

    posted = posted_to_date(tx["posted"])
    amount = Decimal(str(tx["amount"]))
    description = tx.get("description") or ""
    payee = tx.get("payee") or None
    memo = tx.get("memo") or None

    auto_category = await category_service.categorize_transaction_text(
        db, user_id, description, payee
    )

    db.add(
        Transaction(
            account_id=account_db_id,
            transaction_id=str(tx["id"]),
            amount=amount,
            date=posted.date(),
            description=description,
            payee=payee,
            memo=memo,
            auto_category=auto_category,
            is_transfer=auto_category == "Transfers",
        )
    )
    return True


async def run_sync(
    db: AsyncSession,
    connection: SimplefinConnection,
    window_days: int = 2,
    full_sync: bool = False,
) -> dict:
    access_url = decrypt_secret(connection.access_url_encrypted)
    needs_backfill = full_sync or not connection.last_sync_at

    data, api_calls = await _fetch_simplefin_data(
        access_url,
        full_backfill=needs_backfill,
        last_sync_at=connection.last_sync_at,
    )
    user_id = str(connection.user_id)

    account_errors = data.get("errors") or data.get("errlist") or []
    connection.account_errors = account_errors if account_errors else None

    new_count = 0
    for acct in data.get("accounts", []):
        errors = acct.get("errors") or acct.get("errlist")
        if errors:
            acct = {**acct, "extra": errors}
        await _upsert_account(db, connection, acct)

    await db.flush()

    acct_map_result = await db.execute(
        select(Account.account_id, Account.id).where(
            Account.simplefin_connection_id == connection.id
        )
    )
    account_map = {row.account_id: row.id for row in acct_map_result}

    for acct in data.get("accounts", []):
        db_acct_id = account_map.get(str(acct["id"]))
        if not db_acct_id:
            continue
        for tx in acct.get("transactions") or []:
            if await _insert_transaction(db, tx, db_acct_id, user_id):
                new_count += 1

    await category_service.apply_categories_to_new_transactions(db, user_id)
    await category_service.detect_transfers(db, user_id, window_days=window_days)

    connection.last_sync_at = datetime.now(timezone.utc)
    connection.status = "active" if not account_errors else "needs_attention"
    await db.commit()

    await recompute_rollups_for_user(db, user_id)
    logger.info(
        "SimpleFIN sync complete for user %s: %s new txs (%s API calls, backfill=%s)",
        user_id,
        new_count,
        api_calls,
        needs_backfill,
    )
    return {
        "new_transactions": new_count,
        "account_errors": account_errors,
        "api_calls": api_calls,
        "backfill_chunks": api_calls if needs_backfill else 1,
    }


async def setup_connection(
    db: AsyncSession,
    user_id: str,
    setup_token: str | None = None,
    access_url: str | None = None,
) -> SimplefinConnection:
    from app.services.crypto_service import encrypt_secret

    if access_url:
        resolved_url = access_url.strip()
    elif setup_token:
        resolved_url = await simplefin_service.claim_access_url(setup_token)
    else:
        raise ValueError("Either setup_token or access_url is required")

    encrypted = encrypt_secret(resolved_url)

    existing = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == user_id)
    )
    connection = existing.scalar_one_or_none()
    if connection:
        connection.access_url_encrypted = encrypted
        connection.status = "active"
    else:
        connection = SimplefinConnection(
            user_id=user_id,
            access_url_encrypted=encrypted,
        )
        db.add(connection)

    await db.flush()
    return connection
