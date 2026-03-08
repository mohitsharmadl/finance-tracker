"""
Parser for HDFC Bank account statements (CSV and PDF).
CSV columns: Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt, Deposit Amt, Closing Balance
"""
from typing import List, Dict
from .base import BaseParser


class HDFCBankParser(BaseParser):
    SOURCE_NAME = "hdfc_bank"

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
            df = self._read_csv(file_bytes)

        # Normalize column names
        df.columns = [c.strip().lower() for c in df.columns]

        # Map known column variations
        col_map = {}
        for c in df.columns:
            if "date" in c and "value" not in c:
                col_map["date"] = c
            elif "narration" in c or "description" in c:
                col_map["narration"] = c
            elif "withdrawal" in c or "debit" in c:
                col_map["withdrawal"] = c
            elif "deposit" in c or "credit" in c:
                col_map["deposit"] = c

        if "date" not in col_map or "narration" not in col_map:
            raise ValueError("Could not identify required columns in HDFC Bank statement")

        txns = []
        for _, row in df.iterrows():
            date = self._parse_date(str(row.get(col_map["date"], "")))
            if not date:
                continue

            desc = self._clean_description(str(row.get(col_map["narration"], "")))
            if not desc:
                continue

            withdrawal = self._parse_amount(row.get(col_map.get("withdrawal", ""), None))
            deposit = self._parse_amount(row.get(col_map.get("deposit", ""), None))

            if withdrawal:
                txns.append({"date": date, "description": desc, "amount": withdrawal, "txn_type": "debit"})
            elif deposit:
                txns.append({"date": date, "description": desc, "amount": deposit, "txn_type": "credit"})

        return txns

    def _parse_pdf(self, file_bytes: bytes) -> List[Dict]:
        tables = self._extract_pdf_tables(file_bytes)
        txns = []

        for table in tables:
            if not table:
                continue

            # Try to find header row
            header_idx = None
            for i, row in enumerate(table):
                row_text = " ".join(str(c or "") for c in row).lower()
                if "narration" in row_text or ("date" in row_text and "withdrawal" in row_text):
                    header_idx = i
                    break

            if header_idx is None:
                continue

            headers = [str(c or "").strip().lower() for c in table[header_idx]]

            # Find column indices
            date_col = next((i for i, h in enumerate(headers) if "date" in h and "value" not in h), None)
            narr_col = next((i for i, h in enumerate(headers) if "narration" in h or "description" in h), None)
            with_col = next((i for i, h in enumerate(headers) if "withdrawal" in h or "debit" in h), None)
            dep_col = next((i for i, h in enumerate(headers) if "deposit" in h or "credit" in h), None)

            if date_col is None or narr_col is None:
                continue

            for row in table[header_idx + 1:]:
                if len(row) <= max(filter(None, [date_col, narr_col, with_col, dep_col])):
                    continue

                date = self._parse_date(str(row[date_col] or ""))
                if not date:
                    continue

                desc = self._clean_description(str(row[narr_col] or ""))
                if not desc:
                    continue

                withdrawal = self._parse_amount(row[with_col]) if with_col is not None else None
                deposit = self._parse_amount(row[dep_col]) if dep_col is not None else None

                if withdrawal:
                    txns.append({"date": date, "description": desc, "amount": withdrawal, "txn_type": "debit"})
                elif deposit:
                    txns.append({"date": date, "description": desc, "amount": deposit, "txn_type": "credit"})

        return txns
