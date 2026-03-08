"""
Finance Tracker — FastAPI backend.
Tracks personal spending by uploading bank/credit card statements.
"""
import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    COOKIE_NAME, build_google_auth_url, exchange_code_for_token,
    get_user_info, create_session_token, verify_session_token, is_allowed,
)
from app.config import APP_URL
from app.database import get_connection
from app.categorizer import categorize_and_compute_cashback
from app.insights import generate_insights

from app.parsers.hdfc_bank import HDFCBankParser
from app.parsers.icici_bank import ICICIBankParser
from app.parsers.icici_cc import ICICICCParser
from app.parsers.hdfc_cc import HDFCCCParser
from app.parsers.amex_cc import AmexCCParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Finance Tracker", version="1.0.0")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Parser registry — keys must match frontend source values
PARSERS = {
    "hdfc_bank": HDFCBankParser(),
    "icici_bank": ICICIBankParser(),
    "icici_cc": ICICICCParser(),
    "hdfc_cc": HDFCCCParser(),
    "amex_cc": AmexCCParser(),
}

SOURCE_LABELS = {
    "hdfc_bank": "HDFC Bank",
    "icici_bank": "ICICI Bank",
    "icici_cc": "ICICI CC",
    "hdfc_cc": "HDFC CC",
    "amex_cc": "AMEX CC",
}

PUBLIC_PATHS = {"/login", "/auth/google", "/auth/callback", "/auth/logout", "/health"}


# --- Auth middleware ---

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in PUBLIC_PATHS or path.startswith("/static"):
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"error": "Not authenticated"})
        return RedirectResponse("/login")

    email = verify_session_token(token)
    if not email:
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"error": "Invalid or expired session"})
        return RedirectResponse("/login")

    request.state.email = email
    return await call_next(request)


# --- HTML pages ---

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(FRONTEND_DIR, "index.html")) as f:
        return HTMLResponse(f.read())


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open(os.path.join(FRONTEND_DIR, "login.html")) as f:
        return HTMLResponse(f.read())


# --- Auth routes ---

@app.get("/auth/google")
def auth_login():
    return RedirectResponse(url=build_google_auth_url())


@app.get("/auth/callback")
def auth_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return RedirectResponse("/login?error=denied")
    try:
        token_data = exchange_code_for_token(code)
        user_info = get_user_info(token_data["access_token"])
    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return RedirectResponse("/login?error=failed")

    email = user_info.get("email", "")
    if not is_allowed(email):
        return RedirectResponse("/login?error=not_allowed")

    session_token = create_session_token(email)
    response = RedirectResponse(url="/")
    response.set_cookie(
        key=COOKIE_NAME, value=session_token,
        max_age=30 * 24 * 60 * 60, httponly=True, secure=True, samesite="lax",
    )
    return response


@app.get("/auth/logout")
def auth_logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Upload routes ---

@app.post("/api/upload")
async def upload_statement(
    file: UploadFile = File(...),
    source: str = Form(...),
):
    if source not in PARSERS:
        raise HTTPException(400, f"Unknown source: {source}. Valid: {list(PARSERS.keys())}")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "Empty file")

    parser = PARSERS[source]
    try:
        txns = parser.parse(file_bytes, file.filename)
    except Exception as e:
        logger.error(f"Parse error for {source}/{file.filename}: {e}")
        raise HTTPException(400, f"Failed to parse statement: {e}")

    if not txns:
        raise HTTPException(400, "No transactions found in file")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO uploads (filename, source, txn_count, uploaded_at)
               VALUES (%s, %s, %s, NOW()) RETURNING id""",
            (file.filename, source, len(txns)),
        )
        upload_id = cur.fetchone()[0]

        inserted = 0
        skipped = 0
        for txn in txns:
            cat_info = categorize_and_compute_cashback(txn["description"], txn["amount"], source)

            cur.execute(
                """SELECT id FROM transactions
                   WHERE date = %s AND description = %s AND amount = %s AND source = %s""",
                (txn["date"], txn["description"], txn["amount"], source),
            )
            if cur.fetchone():
                skipped += 1
                continue

            cur.execute(
                """INSERT INTO transactions
                   (upload_id, date, description, amount, txn_type, source,
                    category_id, is_coupon, coupon_platform, cashback_amount)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    upload_id, txn["date"], txn["description"], txn["amount"],
                    txn["txn_type"], source, cat_info["category_id"],
                    cat_info["is_coupon"], cat_info["coupon_platform"],
                    cat_info["cashback_amount"],
                ),
            )
            inserted += 1

        cur.execute("UPDATE uploads SET txn_count = %s WHERE id = %s", (inserted, upload_id))
        conn.commit()
        cur.close()

    return {
        "upload_id": upload_id,
        "filename": file.filename,
        "source": source,
        "parsed": len(txns),
        "inserted": inserted,
        "skipped": skipped,
    }


@app.get("/api/uploads")
def list_uploads():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, filename, source, txn_count, uploaded_at
               FROM uploads ORDER BY uploaded_at DESC"""
        )
        rows = cur.fetchall()
        cur.close()
    return {
        "uploads": [
            {
                "id": r[0], "filename": r[1], "source": r[2],
                "txn_count": r[3], "uploaded_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    }


@app.delete("/api/uploads/{upload_id}")
def delete_upload(upload_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE upload_id = %s", (upload_id,))
        cur.execute("DELETE FROM uploads WHERE id = %s RETURNING id", (upload_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
    if not deleted:
        raise HTTPException(404, "Upload not found")
    return {"deleted": upload_id}


# --- Transaction routes ---

@app.get("/api/transactions")
def list_transactions(
    month: Optional[str] = Query(None),  # "YYYY-MM"
    source: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    txn_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    conditions = []
    params = []

    if month:
        conditions.append("TO_CHAR(t.date, 'YYYY-MM') = %s")
        params.append(month)
    if source:
        conditions.append("t.source = %s")
        params.append(source)
    if category_id is not None:
        if category_id == 0:
            conditions.append("t.category_id IS NULL")
        else:
            conditions.append("t.category_id = %s")
            params.append(category_id)
    if txn_type:
        conditions.append("t.txn_type = %s")
        params.append(txn_type)
    if search:
        conditions.append("LOWER(t.description) LIKE %s")
        params.append(f"%{search.lower()}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * per_page

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM transactions t {where}", params)
        total = cur.fetchone()[0]

        # Count uncategorized
        cur.execute("SELECT COUNT(*) FROM transactions WHERE category_id IS NULL")
        uncat_count = cur.fetchone()[0]

        cur.execute(
            f"""SELECT t.id, t.date, t.description, t.amount, t.txn_type, t.source,
                       t.category_id, c.name as category_name,
                       t.is_coupon, t.coupon_platform, t.cashback_amount
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                {where}
                ORDER BY t.date DESC, t.id DESC
                LIMIT %s OFFSET %s""",
            params + [per_page, offset],
        )
        rows = cur.fetchall()
        cur.close()

    return {
        "total": total,
        "uncategorized_count": uncat_count,
        "page": page,
        "per_page": per_page,
        "transactions": [
            {
                "id": r[0],
                "date": r[1].isoformat() if r[1] else None,
                "description": r[2],
                "amount": float(r[3]) if r[3] else 0,
                "txn_type": r[4],
                "source": r[5],
                "category_id": r[6],
                "category_name": r[7],
                "is_coupon": r[8],
                "coupon_platform": r[9],
                "cashback_amount": float(r[10]) if r[10] else None,
            }
            for r in rows
        ],
    }


@app.put("/api/transactions/{txn_id}/category")
async def update_transaction_category(txn_id: int, request: Request):
    body = await request.json()
    category_id = body.get("category_id")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE transactions SET category_id = %s WHERE id = %s RETURNING id",
            (category_id, txn_id),
        )
        updated = cur.fetchone()
        conn.commit()
        cur.close()
    if not updated:
        raise HTTPException(404, "Transaction not found")
    return {"id": txn_id, "category_id": category_id}


# --- Category routes ---

@app.get("/api/categories")
def list_categories():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        rows = cur.fetchall()
        cur.close()
    return {"categories": [{"id": r[0], "name": r[1]} for r in rows]}


# --- Summary ---

@app.get("/api/summary")
def monthly_summary(month: str = Query(...)):
    """Monthly burn summary. month format: YYYY-MM"""
    with get_connection() as conn:
        cur = conn.cursor()

        # Grand totals
        cur.execute(
            """SELECT
                 SUM(CASE WHEN txn_type = 'debit' THEN amount ELSE 0 END),
                 SUM(CASE WHEN txn_type = 'credit' THEN amount ELSE 0 END),
                 SUM(CASE WHEN txn_type = 'debit' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN txn_type = 'credit' THEN 1 ELSE 0 END)
               FROM transactions
               WHERE TO_CHAR(date, 'YYYY-MM') = %s""",
            (month,),
        )
        totals = cur.fetchone()
        total_debit = float(totals[0] or 0)
        total_credit = float(totals[1] or 0)
        debit_count = int(totals[2] or 0)
        credit_count = int(totals[3] or 0)

        # By category (debits only)
        cur.execute(
            """SELECT COALESCE(c.name, 'Uncategorized') as category,
                      SUM(t.amount) as total,
                      COUNT(*) as cnt
               FROM transactions t
               LEFT JOIN categories c ON t.category_id = c.id
               WHERE TO_CHAR(t.date, 'YYYY-MM') = %s AND t.txn_type = 'debit'
               GROUP BY c.name
               ORDER BY total DESC""",
            (month,),
        )
        categories = []
        for r in cur.fetchall():
            categories.append({
                "name": r[0],
                "amount": float(r[1] or 0),
                "count": r[2],
            })

        # Previous month comparison
        parts = month.split("-")
        y, m = int(parts[0]), int(parts[1])
        if m == 1:
            prev_month = f"{y-1}-12"
        else:
            prev_month = f"{y}-{m-1:02d}"

        cur.execute(
            """SELECT COALESCE(c.name, 'Uncategorized') as category, SUM(t.amount) as total
               FROM transactions t
               LEFT JOIN categories c ON t.category_id = c.id
               WHERE TO_CHAR(t.date, 'YYYY-MM') = %s AND t.txn_type = 'debit'
               GROUP BY c.name""",
            (prev_month,),
        )
        prev_totals = {r[0]: float(r[1] or 0) for r in cur.fetchall()}

        for cat in categories:
            prev = prev_totals.get(cat["name"], 0)
            if prev > 0:
                cat["change_pct"] = round(((cat["amount"] - prev) / prev) * 100, 1)
            else:
                cat["change_pct"] = None

        # Top 10 spends
        cur.execute(
            """SELECT date, description, amount, source
               FROM transactions
               WHERE TO_CHAR(date, 'YYYY-MM') = %s AND txn_type = 'debit'
               ORDER BY amount DESC LIMIT 10""",
            (month,),
        )
        top_spends = [
            {
                "date": r[0].isoformat() if r[0] else None,
                "description": r[1], "amount": float(r[2] or 0), "source": r[3],
            }
            for r in cur.fetchall()
        ]

        cur.close()

    return {
        "total_spend": total_debit,
        "total_income": total_credit,
        "spend_count": debit_count,
        "income_count": credit_count,
        "categories": categories,
        "top_spends": top_spends,
    }


# --- Trends ---

@app.get("/api/trends")
def spending_trends(months: int = Query(6, ge=1, le=24)):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT
                 TO_CHAR(date, 'YYYY-MM') as month,
                 SUM(CASE WHEN txn_type = 'debit' THEN amount ELSE 0 END) as total_debit,
                 SUM(CASE WHEN txn_type = 'credit' THEN amount ELSE 0 END) as total_credit,
                 COUNT(*) as cnt
               FROM transactions
               WHERE date >= (CURRENT_DATE - INTERVAL '%s months')
               GROUP BY TO_CHAR(date, 'YYYY-MM')
               ORDER BY month""",
            (months,),
        )
        monthly = []
        for r in cur.fetchall():
            monthly.append({
                "month": r[0],
                "label": _month_label(r[0]),
                "total_spend": float(r[1] or 0),
                "total_income": float(r[2] or 0),
                "txn_count": r[3],
            })

        # By category per month (top 8 categories)
        cur.execute(
            """SELECT COALESCE(c.name, 'Uncategorized') as category, SUM(t.amount) as total
               FROM transactions t
               LEFT JOIN categories c ON t.category_id = c.id
               WHERE t.txn_type = 'debit' AND t.date >= (CURRENT_DATE - INTERVAL '%s months')
               GROUP BY c.name
               ORDER BY total DESC LIMIT 8""",
            (months,),
        )
        top_categories = [r[0] for r in cur.fetchall()]

        cur.execute(
            """SELECT TO_CHAR(t.date, 'YYYY-MM') as month,
                      COALESCE(c.name, 'Uncategorized') as category,
                      SUM(t.amount) as total
               FROM transactions t
               LEFT JOIN categories c ON t.category_id = c.id
               WHERE t.txn_type = 'debit' AND t.date >= (CURRENT_DATE - INTERVAL '%s months')
               GROUP BY TO_CHAR(t.date, 'YYYY-MM'), c.name
               ORDER BY month""",
            (months,),
        )
        cat_by_month = {}
        for r in cur.fetchall():
            m = r[0]
            if m not in cat_by_month:
                cat_by_month[m] = []
            cat_by_month[m].append({"name": r[1], "amount": float(r[2] or 0)})

        for m_data in monthly:
            m_data["by_category"] = cat_by_month.get(m_data["month"], [])

        cur.close()

    return {
        "months": monthly,
        "top_categories": top_categories,
    }


def _month_label(ym: str) -> str:
    parts = ym.split("-")
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return f"{months[int(parts[1])-1]} {parts[0]}"


# --- Insights ---

@app.get("/api/insights")
def get_insights(month: str = Query(None)):
    if month:
        parts = month.split("-")
        y, m = int(parts[0]), int(parts[1])
    else:
        now = datetime.now()
        y, m = now.year, now.month

    insights = generate_insights(y, m)

    # Format for frontend
    category_changes = []
    suggestions = []
    fixed_total = 0
    variable_total = 0
    fixed_cats = {"Rent", "Insurance", "Subscriptions", "EMI / Loans"}

    for i in insights:
        cat = i["category"]
        current = i["current_month_total"]
        previous = i["previous_month_total"]
        change_pct = i.get("change_pct")

        if change_pct is not None:
            category_changes.append({
                "name": cat,
                "current": current,
                "previous": previous,
                "change_pct": change_pct,
            })

        if i.get("flag") == "increase" and change_pct and change_pct > 20:
            saving = i.get("potential_saving", 0)
            suggestions.append({
                "text": f"{cat}: up {change_pct:.0f}% vs last month ({_fmt_inr(previous)} -> {_fmt_inr(current)}). "
                        f"Cutting 20% would save {_fmt_inr(saving)}/month.",
            })

        if cat in fixed_cats:
            fixed_total += current
        else:
            variable_total += current

    return {
        "category_changes": category_changes,
        "suggestions": suggestions,
        "fixed_vs_variable": {"fixed": fixed_total, "variable": variable_total},
    }


def _fmt_inr(v):
    return f"Rs.{v:,.0f}"


# --- iShop / Coupon tracking ---

@app.post("/api/ishop")
async def add_ishop_purchase(request: Request):
    body = await request.json()
    required = ["date", "platform", "amount"]
    for f in required:
        if f not in body:
            raise HTTPException(400, f"Missing field: {f}")

    cashback = round(float(body["amount"]) * 0.18, 2)

    with get_connection() as conn:
        cur = conn.cursor()
        # Get Shopping category id
        cur.execute("SELECT id FROM categories WHERE name = 'Shopping' LIMIT 1")
        row = cur.fetchone()
        cat_id = row[0] if row else None

        cur.execute(
            """INSERT INTO transactions
               (date, description, amount, txn_type, source,
                category_id, is_coupon, coupon_platform, cashback_amount)
               VALUES (%s, %s, %s, 'debit', 'icici_ishop',
                       %s, TRUE, %s, %s)
               RETURNING id""",
            (
                body["date"],
                f"iShop Coupon - {body['platform']}",
                body["amount"],
                cat_id,
                body["platform"],
                cashback,
            ),
        )
        txn_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

    return {"id": txn_id, "cashback_amount": cashback}


@app.get("/api/ishop")
def list_ishop_purchases(month: Optional[str] = Query(None)):
    conditions = ["t.is_coupon = TRUE"]
    params = []

    if month:
        conditions.append("TO_CHAR(t.date, 'YYYY-MM') = %s")
        params.append(month)

    where = f"WHERE {' AND '.join(conditions)}"

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT t.id, t.date, t.description, t.amount,
                       t.coupon_platform, t.cashback_amount
                FROM transactions t
                {where}
                ORDER BY t.date DESC""",
            params,
        )
        rows = cur.fetchall()

        cur.execute(
            f"SELECT SUM(t.amount), SUM(t.cashback_amount), COUNT(*) FROM transactions t {where}",
            params,
        )
        totals = cur.fetchone()
        cur.close()

    return {
        "total_spent": float(totals[0] or 0),
        "total_cashback": float(totals[1] or 0),
        "count": totals[2] or 0,
        "coupons": [
            {
                "id": r[0],
                "date": r[1].isoformat() if r[1] else None,
                "description": r[2],
                "amount": float(r[3]) if r[3] else 0,
                "platform": r[4],
                "cashback_amount": float(r[5]) if r[5] else 0,
            }
            for r in rows
        ],
    }


# --- Available months ---

@app.get("/api/months")
def get_months():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT DISTINCT TO_CHAR(date, 'YYYY-MM') as month
               FROM transactions ORDER BY month DESC"""
        )
        months = [r[0] for r in cur.fetchall()]
        cur.close()
    return {"months": months}


# --- DB init ---

def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                icon VARCHAR(10) DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS category_keywords (
                id SERIAL PRIMARY KEY,
                category_id INTEGER REFERENCES categories(id),
                keyword VARCHAR(200) NOT NULL
            );

            CREATE TABLE IF NOT EXISTS uploads (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(500),
                source VARCHAR(50),
                uploaded_at TIMESTAMP DEFAULT NOW(),
                txn_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                description TEXT NOT NULL,
                amount NUMERIC(12,2) NOT NULL,
                txn_type VARCHAR(10) NOT NULL,
                source VARCHAR(50),
                category_id INTEGER REFERENCES categories(id),
                is_coupon BOOLEAN DEFAULT FALSE,
                coupon_platform VARCHAR(50),
                cashback_amount NUMERIC(10,2),
                upload_id INTEGER REFERENCES uploads(id),
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
            CREATE INDEX IF NOT EXISTS idx_txn_source ON transactions(source);
            CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category_id);
            CREATE INDEX IF NOT EXISTS idx_txn_upload ON transactions(upload_id);
        """)
        conn.commit()

        # Seed default categories if empty
        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            default_categories = [
                "Food & Dining", "Groceries", "Shopping", "Transportation", "Fuel",
                "Utilities", "Rent", "Healthcare", "Entertainment", "Subscriptions",
                "Travel", "Education", "Insurance", "Investments", "EMI / Loans",
                "Personal Care", "Gifts & Donations", "Household",
                "Cash Withdrawal", "Transfer", "Other",
            ]
            for name in default_categories:
                cur.execute("INSERT INTO categories (name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))

            keywords = {
                "Food & Dining": ["swiggy", "zomato", "restaurant", "cafe", "food", "dominos", "pizza", "burger", "starbucks", "mcd", "kfc", "subway", "dunkin"],
                "Groceries": ["bigbasket", "blinkit", "zepto", "dmart", "grocery", "supermarket", "fresh", "nature basket", "jiomart", "instamart"],
                "Shopping": ["amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho", "tatacliq", "reliance digital"],
                "Transportation": ["uber", "ola", "rapido", "metro", "irctc", "railway", "bus"],
                "Fuel": ["fuel", "petrol", "diesel", "hp ", "iocl", "bpcl", "shell"],
                "Utilities": ["electricity", "water", "gas", "broadband", "jio", "airtel", "vi ", "vodafone", "bsnl", "tata play", "dth"],
                "Rent": ["rent", "lease"],
                "Healthcare": ["hospital", "pharmacy", "medical", "doctor", "diagnostic", "lab", "apollo", "pharmeasy", "1mg", "netmeds"],
                "Entertainment": ["netflix", "prime video", "hotstar", "spotify", "youtube", "movie", "pvr", "inox", "book my show"],
                "Subscriptions": ["subscription", "membership", "annual plan", "monthly plan"],
                "Travel": ["hotel", "flight", "makemytrip", "goibibo", "yatra", "cleartrip", "oyo", "booking.com", "airbnb"],
                "Insurance": ["insurance", "lic", "policy", "premium"],
                "Investments": ["mutual fund", "sip", "zerodha", "groww", "kuvera", "nse", "bse", "trading"],
                "EMI / Loans": ["emi", "loan", "interest"],
                "Cash Withdrawal": ["atm", "cash withdrawal", "neft", "imps"],
                "Transfer": ["transfer", "upi"],
            }
            for cat_name, kws in keywords.items():
                cur.execute("SELECT id FROM categories WHERE name = %s", (cat_name,))
                row = cur.fetchone()
                if row:
                    for kw in kws:
                        cur.execute("INSERT INTO category_keywords (category_id, keyword) VALUES (%s, %s)", (row[0], kw))

            conn.commit()

        cur.close()


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Finance Tracker started")
