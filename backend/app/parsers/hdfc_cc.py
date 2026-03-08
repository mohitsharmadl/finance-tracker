"""
Parser for HDFC Credit Card statements (.xls/.csv/.pdf).
Actual format: ~17 header rows, sparse 24-column layout:
  Row 17: col0=Transaction type | col4=Customer Name | col9=Date & Time | col12=Description | col18=REWARDS | col20=AMT | col23=Debit/Credit
  Data from row 18. Date format: DD/MM/YYYY / HH:MM
"""
import re
from typing import List, Dict
from .base import BaseParser


class HDFCCCParser(BaseParser):
    SOURCE_NAME = "hdfc_cc"

    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_pdf(filename):
            return self._parse_pdf(file_bytes)
        return self._parse_excel_csv(file_bytes, filename)

    def _parse_excel_csv(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_excel(filename):
            df = self._read_excel(file_bytes, header=None)
        else:
            df = self._read_csv(file_bytes, header=None)

        # Find header row with "Date & Time" or "Description" + "AMT"
        header_idx = None
        for i, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values).lower()
            if ("date" in row_str and "description" in row_str and "amt" in row_str):
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Could not find header row in HDFC CC statement")

        # Map columns by header text (sparse layout)
        headers = [str(v).strip().lower() if str(v) != "nan" else "" for v in df.iloc[header_idx].values]

        date_col = None
        desc_col = None
        amt_col = None
        dr_cr_col = None

        for i, h in enumerate(headers):
            if "date" in h and "time" in h:
                date_col = i
            elif h == "description":
                desc_col = i
            elif h == "amt":
                amt_col = i
            elif "debit" in h and "credit" in h:
                dr_cr_col = i

        if date_col is None or desc_col is None or amt_col is None:
            raise ValueError("Missing required columns in HDFC CC statement")

        txns = []
        for i in range(header_idx + 1, len(df)):
            row = df.iloc[i]

            # Stop at summary sections
            raw_first = str(row.iloc[0]) if len(row) > 0 else ""
            if "reward" in raw_first.lower() or "summary" in raw_first.lower():
                break

            raw_date = str(row.iloc[date_col]) if date_col < len(row) else ""
            if raw_date == "nan" or not raw_date.strip():
                continue

            # Extract date from "DD/MM/YYYY / HH:MM" format
            date_match = re.search(r"(\d{2}/\d{2}/\d{4})", raw_date)
            if not date_match:
                continue
            date = self._parse_date(date_match.group(1))
            if not date:
                continue

            desc = str(row.iloc[desc_col]) if desc_col < len(row) else ""
            desc = self._clean_description(desc)
            if not desc or desc == "nan":
                continue

            amount = self._parse_amount(row.iloc[amt_col]) if amt_col < len(row) else None
            if not amount:
                continue

            # Determine debit/credit from Debit/Credit column or amount sign
            txn_type = "debit"  # default
            if dr_cr_col is not None and dr_cr_col < len(row):
                dr_cr_val = str(row.iloc[dr_cr_col]).strip().lower()
                if dr_cr_val and dr_cr_val != "nan":
                    if "cr" in dr_cr_val:
                        txn_type = "credit"

            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})

        return txns

    def _parse_pdf(self, file_bytes: bytes) -> List[Dict]:
        text = self._extract_pdf_text(file_bytes)
        txns = []
        pattern = re.compile(
            r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(Cr|Dr|CR|DR)?",
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
            dr_cr = (match.group(4) or "").upper()
            txn_type = "credit" if dr_cr == "CR" else "debit"
            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})
        return txns
