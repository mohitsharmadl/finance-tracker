"""
Base parser and helpers for bank/credit card statement parsing.
"""
import io
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
import pdfplumber


class BaseParser(ABC):
    """Base class for all statement parsers."""

    SOURCE_NAME: str = "unknown"

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        """
        Parse statement file and return list of transaction dicts.
        Each dict: {date, description, amount, txn_type}
        - date: YYYY-MM-DD string
        - description: cleaned transaction narration
        - amount: positive float
        - txn_type: "debit" or "credit"
        """
        pass

    def _is_pdf(self, filename: str) -> bool:
        return filename.lower().endswith(".pdf")

    def _is_csv(self, filename: str) -> bool:
        return filename.lower().endswith(".csv")

    def _is_excel(self, filename: str) -> bool:
        return filename.lower().endswith((".xls", ".xlsx"))

    # --- PDF helpers ---

    def _extract_pdf_tables(self, file_bytes: bytes) -> List[List[List[str]]]:
        """Extract all tables from a PDF. Returns list of tables, each table is list of rows."""
        tables = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
        return tables

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        """Extract raw text from all pages of a PDF."""
        text = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return "\n".join(text)

    # --- CSV/Excel helpers ---

    def _read_csv(self, file_bytes: bytes, **kwargs) -> pd.DataFrame:
        """Read CSV with common defaults for Indian bank statements."""
        defaults = {
            "encoding": "utf-8",
            "skipinitialspace": True,
            "on_bad_lines": "skip",
        }
        defaults.update(kwargs)
        try:
            return pd.read_csv(io.BytesIO(file_bytes), **defaults)
        except UnicodeDecodeError:
            defaults["encoding"] = "latin-1"
            return pd.read_csv(io.BytesIO(file_bytes), **defaults)

    def _read_excel(self, file_bytes: bytes, **kwargs) -> pd.DataFrame:
        """Read Excel file."""
        return pd.read_excel(io.BytesIO(file_bytes), **kwargs)

    # --- Date parsing ---

    DATE_FORMATS = [
        "%d/%m/%Y",     # 01/03/2026
        "%d-%m-%Y",     # 01-03-2026
        "%d/%m/%y",     # 01/03/26
        "%d-%m-%y",     # 01-03-26
        "%d %b %Y",     # 01 Mar 2026
        "%d %b %y",     # 01 Mar 26
        "%d-%b-%Y",     # 01-Mar-2026
        "%d-%b-%y",     # 01-Mar-26
        "%d/%b/%Y",     # 01/Mar/2026
        "%Y-%m-%d",     # 2026-03-01
        "%m/%d/%Y",     # 03/01/2026 (AMEX US format)
    ]

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Try multiple date formats and return YYYY-MM-DD or None."""
        if not date_str or not isinstance(date_str, str):
            return None
        date_str = date_str.strip()
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    # --- Amount parsing ---

    def _parse_amount(self, val) -> Optional[float]:
        """Parse an amount string to float. Returns None if unparseable."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (int, float)):
            return abs(float(val))
        s = str(val).strip()
        if not s or s == "-" or s.lower() == "nan":
            return None
        # Remove commas, currency symbols, spaces
        s = re.sub(r"[,\s₹$]", "", s)
        s = re.sub(r"INR", "", s, flags=re.IGNORECASE)
        # Handle Dr/Cr suffix
        s = re.sub(r"\s*(Dr|Cr|DR|CR)\.?\s*$", "", s)
        s = re.sub(r"^\s*(Dr|Cr|DR|CR)\.?\s*", "", s)
        # Handle parentheses for negative: (100.00)
        if s.startswith("(") and s.endswith(")"):
            s = s[1:-1]
        try:
            return abs(float(s))
        except ValueError:
            return None

    def _clean_description(self, desc) -> str:
        """Clean up a transaction description."""
        if not desc or not isinstance(desc, str):
            return ""
        # Collapse whitespace
        desc = re.sub(r"\s+", " ", desc).strip()
        return desc
