"""
Parser for ICICI Bank account statements (.xls/.csv/.pdf).
Actual format: ~12 header rows, then:
  Row 12 (cols 1-8): [empty] | S No. | Value Date | Transaction Date | Cheque Number | Transaction Remarks | Withdrawal Amount(INR) | Deposit Amount(INR) | Balance(INR)
  Data from row 13. Date format: DD/MM/YYYY
"""
from typing import List, Dict
from .base import BaseParser


class ICICIBankParser(BaseParser):
    SOURCE_NAME = "icici_bank"

    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_pdf(filename):
            return self._parse_pdf(file_bytes)
        return self._parse_excel_csv(file_bytes, filename)

    def _parse_excel_csv(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_excel(filename):
            df = self._read_excel(file_bytes, header=None)
        else:
            df = self._read_csv(file_bytes, header=None)

        # Find header row containing BOTH "Transaction Remarks" AND "Withdrawal"
        header_idx = None
        for i, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values).lower()
            if "withdrawal" in row_str and "deposit" in row_str and "date" in row_str:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Could not find header row in ICICI Bank statement")

        headers = [str(v).strip().lower() if str(v) != "nan" else "" for v in df.iloc[header_idx].values]

        # Find columns by header text
        date_col = None
        remarks_col = None
        withdrawal_col = None
        deposit_col = None

        for i, h in enumerate(headers):
            if "transaction date" in h:
                date_col = i
            elif "value date" in h and date_col is None:
                date_col = i
            elif "transaction remarks" in h or "remarks" in h:
                remarks_col = i
            elif "withdrawal" in h:
                withdrawal_col = i
            elif "deposit" in h:
                deposit_col = i

        if date_col is None or remarks_col is None:
            raise ValueError("Missing required columns in ICICI Bank statement")

        txns = []
        for i in range(header_idx + 1, len(df)):
            row = df.iloc[i]

            raw_date = str(row.iloc[date_col]) if date_col < len(row) else ""
            if raw_date == "nan" or not raw_date.strip():
                continue

            date = self._parse_date(raw_date.strip())
            if not date:
                continue

            desc = self._clean_description(str(row.iloc[remarks_col]) if remarks_col < len(row) else "")
            if not desc or desc == "nan":
                continue

            withdrawal = self._parse_amount(row.iloc[withdrawal_col]) if withdrawal_col is not None and withdrawal_col < len(row) else None
            deposit = self._parse_amount(row.iloc[deposit_col]) if deposit_col is not None and deposit_col < len(row) else None

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
                if "date" in row_text and ("withdrawal" in row_text or "debit" in row_text):
                    header_idx = i
                    break
            if header_idx is None:
                continue
            headers = [str(c or "").strip().lower() for c in table[header_idx]]
            date_col = next((i for i, h in enumerate(headers) if "date" in h and "value" not in h), None)
            desc_col = next((i for i, h in enumerate(headers) if "remark" in h or "description" in h or "particular" in h), None)
            debit_col = next((i for i, h in enumerate(headers) if "withdrawal" in h or "debit" in h), None)
            credit_col = next((i for i, h in enumerate(headers) if "deposit" in h or "credit" in h), None)
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
