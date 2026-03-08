"""
Parser for American Express Credit Card statements (CSV).
CSV columns: Date, Description, Amount (credits are negative)
"""
from typing import List, Dict
from .base import BaseParser


class AmexCCParser(BaseParser):
    SOURCE_NAME = "amex_cc"

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

        df.columns = [c.strip().lower() for c in df.columns]

        # AMEX CSV typically has: Date, Description, Amount
        # Some variations: Date, Reference, Description, Amount
        date_col = next((c for c in df.columns if "date" in c), None)
        desc_col = next((c for c in df.columns if "description" in c or "particular" in c), None)
        amt_col = next((c for c in df.columns if "amount" in c), None)

        if not date_col or not amt_col:
            raise ValueError("Could not identify columns in AMEX statement")

        # If no description column, try 'reference' or second column
        if not desc_col:
            desc_col = next((c for c in df.columns if "reference" in c or "detail" in c), None)
            if not desc_col:
                # Use second column as description
                desc_col = df.columns[1] if len(df.columns) > 1 else None

        if not desc_col:
            raise ValueError("Could not identify description column in AMEX statement")

        txns = []
        for _, row in df.iterrows():
            date = self._parse_date(str(row.get(date_col, "")))
            if not date:
                continue

            desc = self._clean_description(str(row.get(desc_col, "")))
            if not desc:
                continue

            raw_amt = row.get(amt_col)
            if raw_amt is None:
                continue

            # AMEX: positive = debit (charge), negative = credit (payment/refund)
            try:
                amt_float = float(str(raw_amt).replace(",", "").replace("₹", "").replace("$", "").strip())
            except ValueError:
                continue

            if amt_float == 0:
                continue

            txn_type = "credit" if amt_float < 0 else "debit"
            amount = abs(amt_float)

            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})

        return txns

    def _parse_pdf(self, file_bytes: bytes) -> List[Dict]:
        """Best-effort PDF parsing for AMEX."""
        import re
        text = self._extract_pdf_text(file_bytes)
        txns = []

        # Pattern: DD Mon YYYY or DD/MM/YYYY followed by description and amount
        pattern = re.compile(
            r"(\d{2}\s+\w{3}\s+\d{4}|\d{2}[/-]\d{2}[/-]\d{4})\s+(.+?)\s+([\-]?[\d,]+\.?\d*)\s*$",
            re.MULTILINE,
        )
        for match in pattern.finditer(text):
            date = self._parse_date(match.group(1))
            if not date:
                continue
            desc = self._clean_description(match.group(2))
            amount_str = match.group(3).replace(",", "")
            try:
                amt_float = float(amount_str)
            except ValueError:
                continue
            if amt_float == 0:
                continue
            txn_type = "credit" if amt_float < 0 else "debit"
            txns.append({"date": date, "description": desc, "amount": abs(amt_float), "txn_type": txn_type})

        return txns
