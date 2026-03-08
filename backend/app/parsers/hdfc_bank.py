"""
Parser for HDFC Bank account statements (.xls/.csv/.pdf).
Actual format: ~20 header rows, then:
  Row 20: Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance
  Data starts row 22. Date format: DD/MM/YY
"""
from typing import List, Dict
from .base import BaseParser


class HDFCBankParser(BaseParser):
    SOURCE_NAME = "hdfc_bank"

    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_pdf(filename):
            return self._parse_pdf(file_bytes)
        return self._parse_excel_csv(file_bytes, filename)

    def _parse_excel_csv(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_excel(filename):
            df = self._read_excel(file_bytes, header=None)
        else:
            df = self._read_csv(file_bytes, header=None)

        # Find header row containing "Narration"
        header_idx = None
        for i, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values).lower()
            if "narration" in row_str and "date" in row_str:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Could not find header row in HDFC Bank statement")

        # Map columns by header text
        headers = [str(v).strip().lower() if str(v) != "nan" else "" for v in df.iloc[header_idx].values]
        date_col = next((i for i, h in enumerate(headers) if h.startswith("date")), None)
        narr_col = next((i for i, h in enumerate(headers) if "narration" in h), None)
        with_col = next((i for i, h in enumerate(headers) if "withdrawal" in h), None)
        dep_col = next((i for i, h in enumerate(headers) if "deposit" in h), None)

        if date_col is None or narr_col is None:
            raise ValueError("Missing date/narration columns in HDFC Bank statement")

        txns = []
        for i in range(header_idx + 1, len(df)):
            row = df.iloc[i]

            # Skip separator rows (asterisks)
            raw_date = str(row.iloc[date_col]) if date_col < len(row) else ""
            if "***" in raw_date or raw_date == "nan" or not raw_date.strip():
                continue

            date = self._parse_date(raw_date.strip())
            if not date:
                continue

            desc = self._clean_description(str(row.iloc[narr_col]) if narr_col < len(row) else "")
            if not desc or desc == "nan":
                continue

            withdrawal = self._parse_amount(row.iloc[with_col]) if with_col is not None and with_col < len(row) else None
            deposit = self._parse_amount(row.iloc[dep_col]) if dep_col is not None and dep_col < len(row) else None

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
            header_idx = None
            for i, row in enumerate(table):
                row_text = " ".join(str(c or "") for c in row).lower()
                if "narration" in row_text and "date" in row_text:
                    header_idx = i
                    break
            if header_idx is None:
                continue
            headers = [str(c or "").strip().lower() for c in table[header_idx]]
            date_col = next((i for i, h in enumerate(headers) if h.startswith("date")), None)
            narr_col = next((i for i, h in enumerate(headers) if "narration" in h), None)
            with_col = next((i for i, h in enumerate(headers) if "withdrawal" in h), None)
            dep_col = next((i for i, h in enumerate(headers) if "deposit" in h), None)
            if date_col is None or narr_col is None:
                continue
            for row in table[header_idx + 1:]:
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
