"""
Category resolution and transfer detection for SimpleFIN transactions.
"""
import re
from datetime import timedelta

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_override import CategoryOverride
from app.models.merchant_category_rule import MerchantCategoryRule
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.simplefin_connection import SimplefinConnection

CATEGORIES = [
    "Income",
    "Food & Drink",
    "Transport",
    "Shopping",
    "Bills & Utilities",
    "Entertainment",
    "Health",
    "Travel",
    "Services",
    "Home",
    "Personal Care",
    "Education",
    "Bank Fees",
    "Debt Payments",
    "Transfers",
    "Uncategorized",
]

SEED_RULES: list[tuple[str, str, bool]] = [
    ("STARBUCKS", "Food & Drink", False),
    ("DUNKIN", "Food & Drink", False),
    ("MCDONALD", "Food & Drink", False),
    ("CHIPOTLE", "Food & Drink", False),
    ("DOORDASH", "Food & Drink", False),
    ("UBER EATS", "Food & Drink", False),
    ("GRUBHUB", "Food & Drink", False),
    ("TRADER JOE", "Food & Drink", False),
    ("WHOLE FOODS", "Food & Drink", False),
    ("SAFEWAY", "Food & Drink", False),
    ("KROGER", "Food & Drink", False),
    ("COSTCO", "Food & Drink", False),
    ("SHELL OIL", "Transport", False),
    ("CHEVRON", "Transport", False),
    ("EXXON", "Transport", False),
    ("UBER", "Transport", False),
    ("LYFT", "Transport", False),
    ("METRO", "Transport", False),
    ("PARKING", "Transport", False),
    ("AMAZON", "Shopping", False),
    ("TARGET", "Shopping", False),
    ("WALMART", "Shopping", False),
    ("BEST BUY", "Shopping", False),
    ("APPLE.COM", "Shopping", False),
    ("NETFLIX", "Entertainment", False),
    ("SPOTIFY", "Entertainment", False),
    ("HULU", "Entertainment", False),
    ("DISNEY", "Entertainment", False),
    ("CVS", "Health", False),
    ("WALGREENS", "Health", False),
    ("KAISER", "Health", False),
    ("ELECTRIC", "Bills & Utilities", False),
    ("PG&E", "Bills & Utilities", False),
    ("COMCAST", "Bills & Utilities", False),
    ("XFINITY", "Bills & Utilities", False),
    ("AT&T", "Bills & Utilities", False),
    ("VERIZON", "Bills & Utilities", False),
    ("T-MOBILE", "Bills & Utilities", False),
    ("RENT", "Bills & Utilities", False),
    ("MORTGAGE", "Debt Payments", False),
    ("PAYROLL", "Income", False),
    ("DIRECT DEP", "Income", False),
    ("DIR DEP", "Income", False),
    ("EXP REIMB", "Income", False),
    ("ALTAIR", "Income", False),
    ("SALARY", "Income", False),
    ("INTEREST PAID", "Income", False),
    ("DIVIDEND", "Income", False),
    ("TRANSFER", "Transfers", False),
    ("PAYMENT", "Transfers", False),
    ("CREDIT CARD", "Transfers", False),
    ("AUTOPAY", "Transfers", False),
    ("ZELLE", "Transfers", False),
    ("VENMO", "Transfers", False),
    ("PAYPAL", "Transfers", False),
    ("OVERDRAFT", "Bank Fees", False),
    ("SERVICE FEE", "Bank Fees", False),
    ("ATM FEE", "Bank Fees", False),
    # Travel
    ("CHEWUCH", "Travel", False),
    ("HOTEL", "Travel", False),
    (" INN ", "Travel", False),
    ("AIRBNB", "Travel", False),
    # Shopping
    ("NIKE", "Shopping", False),
    ("H&M", "Shopping", False),
    ("FABLETICS", "Shopping", False),
    ("STOCKX", "Shopping", False),
    # Food
    ("CHILI", "Food & Drink", False),
    ("THAI CUISINE", "Food & Drink", False),
    ("SPARROW", "Food & Drink", False),
    ("BOLLYWOOD", "Food & Drink", False),
    ("7-ELEVEN", "Food & Drink", False),
    ("SALT AND STRAW", "Food & Drink", False),
    ("GINGER & SCALLION", "Food & Drink", False),
    ("FUJI BAKERY", "Food & Drink", False),
    ("TRINITY MARKET", "Food & Drink", False),
    # Entertainment
    ("GOOGLE PLAY", "Entertainment", False),
    ("GREAT WESTERN", "Entertainment", False),
    ("TIKTOK SHOP", "Shopping", False),
    # Education / income
    ("GEORGIA INSTITUT", "Income", False),
    ("CASHREWARD", "Income", False),
    ("INTEREST EARNED", "Income", False),
    # Services
    ("RAILWAY", "Services", False),
    ("ORCA", "Transport", False),
    ("EXPO.DEV", "Services", False),
    ("WSFERRIES", "Transport", False),
    ("TST*", "Food & Drink", False),
    ("TACO BELL", "Food & Drink", False),
    ("PANDA EXPRESS", "Food & Drink", False),
    ("CHICK-FIL", "Food & Drink", False),
    ("RAISING CANES", "Food & Drink", False),
    ("BUFFALO WILD", "Food & Drink", False),
    ("CAVA", "Food & Drink", False),
    ("PUBLIX", "Food & Drink", False),
    ("GYRO", "Food & Drink", False),
    ("TACOS", "Food & Drink", False),
    ("HOT CHICKEN", "Food & Drink", False),
    ("SANDO", "Food & Drink", False),
    ("SKALKA", "Food & Drink", False),
    ("MOGE TEE", "Food & Drink", False),
    ("ALPHA KAPPA", "Education", False),
]


async def seed_merchant_rules(db: AsyncSession) -> None:
    existing = await db.execute(select(MerchantCategoryRule.pattern))
    known = {row.pattern for row in existing}
    for i, (pattern, category, is_regex) in enumerate(SEED_RULES):
        if pattern in known:
            continue
        db.add(
            MerchantCategoryRule(
                pattern=pattern,
                category=category,
                is_regex=is_regex,
                priority=i,
            )
        )
    await db.flush()


def _match_text(text: str, pattern: str, is_regex: bool) -> bool:
    if is_regex:
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            return False
    return pattern.upper() in text.upper()


def _smart_category(description: str, payee: str | None) -> str | None:
    """High-confidence patterns before generic merchant rules."""
    text = f"{description} {payee or ''}".upper()

    income_markers = (
        "DIR DEP",
        "DIRECT DEP",
        "PAYROLL",
        "EXP REIMB",
        "EDI PYMNTS",
        "CASHREWARD",
        "INTEREST EARNED",
        "INTEREST PAID",
        "DIVIDEND",
    )
    if any(m in text for m in income_markers):
        return "Income"

    # Expedia payroll uses DIR DEP; travel bookings are card charges
    if "EXPEDIA" in text and not any(m in text for m in ("DIR DEP", "DIRECT DEP", "EXP REIMB")):
        return "Travel"

    return None


async def categorize_transaction_text(
    db: AsyncSession,
    user_id: str,
    description: str,
    payee: str | None,
) -> str:
    text = f"{description} {payee or ''}".strip()

    smart = _smart_category(description, payee)
    if smart:
        return smart

    if payee:
        override_result = await db.execute(
            select(CategoryOverride)
            .where(CategoryOverride.user_id == user_id)
            .order_by(CategoryOverride.created_at.desc())
        )
        for override in override_result.scalars():
            if payee.lower().startswith(override.merchant_name_pattern.lower()):
                return override.override_category
            if override.merchant_name_pattern.lower() in text.lower():
                return override.override_category

    rules_result = await db.execute(
        select(MerchantCategoryRule).order_by(MerchantCategoryRule.priority)
    )
    for rule in rules_result.scalars():
        if _match_text(text, rule.pattern, rule.is_regex):
            return rule.category

    return "Uncategorized"


async def apply_categories_to_new_transactions(
    db: AsyncSession, user_id: str, transaction_ids: list[str] | None = None
) -> int:
    account_ids_result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == user_id)
    )
    account_ids = [row.id for row in account_ids_result]
    if not account_ids:
        return 0

    filters = [
        Transaction.account_id.in_(account_ids),
        Transaction.user_category.is_(None),
        or_(Transaction.auto_category.is_(None), Transaction.auto_category == "Uncategorized"),
    ]
    if transaction_ids:
        filters.append(Transaction.transaction_id.in_(transaction_ids))

    result = await db.execute(select(Transaction).where(and_(*filters)))
    updated = 0
    for tx in result.scalars():
        tx.auto_category = await categorize_transaction_text(
            db, user_id, tx.description, tx.payee
        )
        updated += 1
    await db.flush()
    return updated


async def recategorize_uncategorized(db: AsyncSession, user_id: str) -> int:
    """Re-run rules on all non-transfer txs still marked Uncategorized."""
    account_ids_result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == user_id)
    )
    account_ids = [row.id for row in account_ids_result]
    if not account_ids:
        return 0

    result = await db.execute(
        select(Transaction).where(
            Transaction.account_id.in_(account_ids),
            Transaction.user_category.is_(None),
            Transaction.is_transfer == False,  # noqa: E712
            or_(
                Transaction.auto_category.is_(None),
                Transaction.auto_category == "Uncategorized",
            ),
        )
    )
    updated = 0
    for tx in result.scalars():
        new_cat = await categorize_transaction_text(db, user_id, tx.description, tx.payee)
        if new_cat != tx.auto_category:
            tx.auto_category = new_cat
            updated += 1
    await db.flush()
    return updated


async def detect_transfers(db: AsyncSession, user_id: str, window_days: int = 2) -> int:
    """Pair opposite-sign, same-amount transactions across accounts within a date window."""
    account_ids_result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == user_id)
    )
    account_ids = [row.id for row in account_ids_result]
    if len(account_ids) < 2:
        return 0

    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.account_id.in_(account_ids),
            Transaction.transfer_manual_override == False,  # noqa: E712
        )
        .order_by(Transaction.date)
    )
    txs = list(result.scalars())
    paired: set[str] = set()
    marked = 0

    def _is_payroll(tx: Transaction) -> bool:
        if tx.auto_category == "Income" or tx.user_category == "Income":
            return True
        text = f"{tx.description} {tx.payee or ''}".upper()
        return any(k in text for k in ("DIR DEP", "DIRECT DEP", "PAYROLL", "EXP REIMB"))

    for i, tx_a in enumerate(txs):
        if tx_a.transaction_id in paired or tx_a.is_transfer:
            continue
        if tx_a.amount == 0 or _is_payroll(tx_a):
            continue

        for tx_b in txs[i + 1 :]:
            if tx_b.transaction_id in paired or tx_b.is_transfer:
                continue
            if tx_b.amount == 0 or _is_payroll(tx_b):
                continue
            if tx_a.account_id == tx_b.account_id:
                continue
            if tx_a.amount + tx_b.amount != 0:
                continue
            if abs((tx_b.date - tx_a.date).days) > window_days:
                if tx_b.date > tx_a.date:
                    break
                continue

            tx_a.is_transfer = True
            tx_b.is_transfer = True
            if tx_a.auto_category != "Income":
                tx_a.auto_category = "Transfers"
            if tx_b.auto_category != "Income":
                tx_b.auto_category = "Transfers"
            paired.add(tx_a.transaction_id)
            paired.add(tx_b.transaction_id)
            marked += 2
            break

    await db.flush()
    return marked
