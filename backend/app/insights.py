"""
Generate spending insights and "where to cut back" analysis.
"""
import logging
from typing import List, Dict
from app.database import get_connection

logger = logging.getLogger(__name__)


def get_monthly_category_totals(year: int, month: int) -> Dict[str, float]:
    """Get total debit amount per category for a given month."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(c.name, 'Uncategorized') as category, SUM(t.amount) as total
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE EXTRACT(YEAR FROM t.date) = %s
              AND EXTRACT(MONTH FROM t.date) = %s
              AND t.txn_type = 'debit'
            GROUP BY c.name
            ORDER BY total DESC
        """, (year, month))
        rows = cur.fetchall()
        cur.close()
    return {row[0]: float(row[1]) for row in rows}


def get_previous_month(year: int, month: int):
    """Return (year, month) for the previous month."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def generate_insights(year: int, month: int) -> List[Dict]:
    """
    Compare current month vs previous month per category.
    Flag categories with >20% increase.
    Suggest 20% cut savings.
    """
    prev_year, prev_month = get_previous_month(year, month)

    current = get_monthly_category_totals(year, month)
    previous = get_monthly_category_totals(prev_year, prev_month)

    insights = []

    for category, current_total in current.items():
        prev_total = previous.get(category, 0)

        insight = {
            "category": category,
            "current_month_total": round(current_total, 2),
            "previous_month_total": round(prev_total, 2),
            "change_amount": round(current_total - prev_total, 2),
            "change_pct": None,
            "flag": None,
            "potential_saving": round(current_total * 0.20, 2),
        }

        if prev_total > 0:
            change_pct = ((current_total - prev_total) / prev_total) * 100
            insight["change_pct"] = round(change_pct, 1)

            if change_pct > 20:
                insight["flag"] = "increase"
            elif change_pct < -20:
                insight["flag"] = "decrease"
        elif current_total > 0:
            insight["flag"] = "new"

        insights.append(insight)

    # Sort: flagged increases first, then by current total descending
    def sort_key(i):
        flag_order = {"increase": 0, "new": 1, None: 2, "decrease": 3}
        return (flag_order.get(i["flag"], 2), -i["current_month_total"])

    insights.sort(key=sort_key)

    return insights
