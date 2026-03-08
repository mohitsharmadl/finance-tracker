"""
Parser for ICICI Bank account statements (CSV and PDF).
CSV columns: Transaction Date, Value Date, Description, Debit, Credit, Balance
"""
from typing import List, Dict
from .base import BaseParser


class ICICIBankParser(BaseParser):
    SOURCE_NAME = "icici_bank"

    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_csv(filename) or self._is_excel(filename):
            return self._parse_csv(file_bytes, filename)
        elif self._is_pdf(filename):
            return self._parse_pdf(file_bytes)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

    def _parse_csv(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_excel(filename):
            df = self._read_excel(file_bytes)
        else:
            # ICICI sometimes has extra header rows; try skipping
            df = self._read_csv(file_bytes)
            # If columns don't look right, try skipping rows
            if not any("date" in str(c).lower() for c in df.columns):
                for skip in range(1, 10):
                    df = self._read_csv(file_bytes, skiprows=skip)
                    if any("date" in str(c).lower() for c in df.columns):
                        break

        df.columns = [c.strip().lower() for c in df.columns]

        col_map = {}
        for c in df.columns:
            if "transaction" in c and "date" in c:
                col_map["date"] = c
            elif c == "date":
                col_map.setdefault("date", c)
            elif "description" in c or "particulars" in c or "narration" in c:
                col_map["description"] = c
            elif "debit" in c or "withdrawal" in c:
                col_map["debit"] = c
            elif "credit" in c or "deposit" in c:
                col_map["credit"] = c

        if "date" not in col_map or "description" not in col_map:
            raise ValueError("Could not identify required columns in ICICI Bank statement")

        txns = []
        for _, row in df.iterrows():
            date = self._parse_date(str(row.get(col_map["date"], "")))
            if not date:
                continue

            desc = self._clean_description(str(row.get(col_map["description"], "")))
            if not desc:
                continue

            debit = self._parse_amount(row.get(col_map.get("debit", ""), None))
            credit = self._parse_amount(row.get(col_map.get("credit", ""), None))

            if debit:
                txns.append({"date": date, "description": desc, "amount": debit, "txn_type": "debit"})
            elif credit:
                txns.append({"date": date, "description": desc, "amount": credit, "txn_type": "credit"})

        return txns

    def _parse_pdf(self, file_bytes: bytes) -> List[Dict]:
        tables = self._extract_pdf_tables(file_bytes)
        txns = []

        for table in tables:
            if not table:
                continue

            header_idx = None
            for i, row in enumerate(table):
                row_text = " ".join(str(c or "") for c in row).lower()
                if "date" in row_text and ("debit" in row_text or "withdrawal" in row_text):
                    header_idx = i
                    break

            if header_idx is None:
                continue

            headers = [str(c or "").strip().lower() for c in table[header_idx]]

            date_col = next((i for i, h in enumerate(headers) if "date" in h and "value" not in h), None)
            desc_col = next((i for i, h in enumerate(headers) if "description" in h or "particular" in h), None)
            debit_col = next((i for i, h in enumerate(headers) if "debit" in h or "withdrawal" in h), None)
            credit_col = next((i for i, h in enumerate(headers) if "credit" in h or "deposit" in h), None)

            if date_col is None or desc_col is None:
                continue

            for row in table[header_idx + 1:]:
                if len(row) <= max(filter(None, [date_col, desc_col, debit_col, credit_col])):
                    continue

                date = self._parse_date(str(row[date_col] or ""))
                if not date:
                    continue

                desc = self._clean_description(str(row[desc_col] or ""))
                if not desc:
                    continue

                debit = self._parse_amount(row[debit_col]) if debit_col is not None else None
                credit = self._parse_amount(row[credit_col]) if credit_col is not None else None

                if debit:
                    txns.append({"date": date, "description": desc, "amount": debit, "txn_type": "debit"})
                elif credit:
                    txns.append({"date": date, "description": desc, "amount": credit, "txn_type": "credit"})

        return txns
