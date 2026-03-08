"""
Parser for ICICI Credit Card statements (.xls/.csv/.pdf).
Actual format: ~15 header rows, sparse 14-column layout:
  Row 15: col1=Transaction Date | col5=Details | col9=Amount (INR) | col13=Reference Number
  Data from row 17 (row 16 is blank). Date format: DD-MM-YYYY
  Amounts have "Dr." or "Cr." suffix.
"""
import re
from typing import List, Dict
from .base import BaseParser


class ICICICCParser(BaseParser):
    SOURCE_NAME = "icici_cc"

    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_pdf(filename):
            return self._parse_pdf(file_bytes)
        return self._parse_excel_csv(file_bytes, filename)

    def _parse_excel_csv(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_excel(filename):
            df = self._read_excel(file_bytes, header=None)
        else:
            df = self._read_csv(file_bytes, header=None)

        # Find header row with "Transaction Date" and "Amount"
        header_idx = None
        for i, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values).lower()
            if "transaction date" in row_str and "amount" in row_str:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Could not find header row in ICICI CC statement")

        # Map sparse columns by header text
        headers = [str(v).strip().lower() if str(v) != "nan" else "" for v in df.iloc[header_idx].values]

        date_col = None
        details_col = None
        amount_col = None

        for i, h in enumerate(headers):
            if "transaction date" in h:
                date_col = i
            elif h == "details" or "detail" in h:
                details_col = i
            elif "amount" in h:
                amount_col = i

        if date_col is None or details_col is None or amount_col is None:
            raise ValueError("Missing required columns in ICICI CC statement")

        txns = []
        for i in range(header_idx + 1, len(df)):
            row = df.iloc[i]

            raw_date = str(row.iloc[date_col]) if date_col < len(row) else ""
            if raw_date == "nan" or not raw_date.strip():
                continue

            date = self._parse_date(raw_date.strip())
            if not date:
                continue

            desc = str(row.iloc[details_col]) if details_col < len(row) else ""
            desc = self._clean_description(desc)
            if not desc or desc == "nan":
                continue

            raw_amount = str(row.iloc[amount_col]) if amount_col < len(row) else ""
            if raw_amount == "nan" or not raw_amount.strip():
                continue

            # Parse amount and Dr./Cr. suffix
            # Format: "3382.5 Dr." or "8040.44 Cr."
            is_credit = bool(re.search(r"cr\.?", raw_amount, re.IGNORECASE))
            amount = self._parse_amount(raw_amount)
            if not amount:
                continue

            txn_type = "credit" if is_credit else "debit"
            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})

        return txns

    def _parse_pdf(self, file_bytes: bytes) -> List[Dict]:
        text = self._extract_pdf_text(file_bytes)
        txns = []
        pattern = re.compile(
            r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(Dr|Cr|DR|CR)\.?",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            date = self._parse_date(match.group(1))
            if not date:
                continue
            desc = self._clean_description(match.group(2))
            amount = self._parse_amount(match.group(3))
            if not amount:
                continue
            dr_cr = match.group(4).upper()
            txn_type = "credit" if dr_cr == "CR" else "debit"
            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})
        return txns
