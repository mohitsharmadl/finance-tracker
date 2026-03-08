"""
Auto-categorize transactions based on keyword matching from DB.
Also detects iShop coupon purchases.
"""
import logging
from typing import Optional, Tuple
from app.database import get_connection

logger = logging.getLogger(__name__)

# Platforms eligible for iShop coupon detection (ICICI iShop)
ISHOP_PLATFORMS = {
    "amazon": "Amazon",
    "blinkit": "Blinkit",
    "flipkart": "Flipkart",
    "bigbasket": "BigBasket",
    "uber": "Uber",
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "myntra": "Myntra",
    "ajio": "Ajio",
    "nykaa": "Nykaa",
    "jiomart": "JioMart",
    "dunzo": "Dunzo",
    "zepto": "Zepto",
}

ISHOP_CASHBACK_RATE = 0.18  # 18% cashback on iShop coupons


def load_category_keywords() -> list:
    """Load categories and their keywords from DB."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, ck.keyword
            FROM categories c
            JOIN category_keywords ck ON c.id = ck.category_id
            ORDER BY LENGTH(ck.keyword) DESC
        """)
        rows = cur.fetchall()
        cur.close()
    return rows


def categorize_transaction(description: str, source: str = "") -> dict:
    """
    Categorize a transaction by matching description against keywords.
    Returns: {category_id, is_coupon, coupon_platform, cashback_amount}
    """
    desc_lower = description.lower()
    result = {
        "category_id": None,
        "is_coupon": False,
        "coupon_platform": None,
        "cashback_amount": None,
    }

    # Check if it's an iShop coupon purchase
    is_ishop = "ishop" in desc_lower

    # Also detect ICICI + known platform as iShop
    if not is_ishop and "icici" in source.lower():
        for key in ISHOP_PLATFORMS:
            if key in desc_lower:
                is_ishop = True
                break

    if is_ishop:
        result["is_coupon"] = True
        # Detect which platform
        for key, platform in ISHOP_PLATFORMS.items():
            if key in desc_lower:
                result["coupon_platform"] = platform
                break

    # Load keywords and match
    keywords = load_category_keywords()
    best_match_len = 0
    best_category_id = None

    for cat_id, cat_name, keyword in keywords:
        kw_lower = keyword.lower()
        if kw_lower in desc_lower and len(kw_lower) > best_match_len:
            best_match_len = len(kw_lower)
            best_category_id = cat_id

    result["category_id"] = best_category_id
    return result


def categorize_and_compute_cashback(description: str, amount: float, source: str = "") -> dict:
    """
    Categorize + compute cashback for iShop coupon purchases.
    """
    result = categorize_transaction(description, source)
    if result["is_coupon"] and amount:
        result["cashback_amount"] = round(amount * ISHOP_CASHBACK_RATE, 2)
    return result
