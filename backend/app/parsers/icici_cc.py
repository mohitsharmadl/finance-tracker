"""
Parser for ICICI Credit Card statements (PDF).
PDF table: Date, Description, Amount (Dr/Cr)
"""
import re
from typing import List, Dict
from .base import BaseParser


class ICICICCParser(BaseParser):
    SOURCE_NAME = "icici_cc"

    def parse(self, file_bytes: bytes, filename: str) -> List[Dict]:
        if self._is_pdf(filename):
            return self._parse_pdf(file_bytes)
        elif self._is_csv(filename) or self._is_excel(filename):
            return self._parse_csv(file_bytes, filename)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

    def _parse_pdf(self, file_bytes: bytes) -> List[Dict]:
        tables = self._extract_pdf_tables(file_bytes)
        txns = []

        for table in tables:
            if not table:
                continue

            # Find header
            header_idx = None
            for i, row in enumerate(table):
                row_text = " ".join(str(c or "") for c in row).lower()
                if "date" in row_text and "amount" in row_text:
                    header_idx = i
                    break

            if header_idx is None:
                # Try parsing without header (some ICICI CC PDFs have no table headers per page)
                for row in table:
                    txn = self._parse_row_heuristic(row)
                    if txn:
                        txns.append(txn)
                continue

            headers = [str(c or "").strip().lower() for c in table[header_idx]]

            date_col = next((i for i, h in enumerate(headers) if "date" in h), None)
            desc_col = next((i for i, h in enumerate(headers) if "description" in h or "particular" in h or "detail" in h), None)
            amt_col = next((i for i, h in enumerate(headers) if "amount" in h), None)

            if date_col is None:
                continue

            for row in table[header_idx + 1:]:
                if len(row) <= max(filter(None, [date_col, desc_col, amt_col])):
                    continue

                date = self._parse_date(str(row[date_col] or ""))
                if not date:
                    continue

                desc = self._clean_description(str(row[desc_col] or "")) if desc_col is not None else ""
                if not desc:
                    continue

                amt_str = str(row[amt_col] or "") if amt_col is not None else ""
                amount = self._parse_amount(amt_str)
                if not amount:
                    continue

                # Determine Dr/Cr from amount string
                txn_type = "credit" if re.search(r"(Cr|CR)", amt_str) else "debit"

                txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})

        # Fallback: try text-based parsing if no tables found
        if not txns:
            txns = self._parse_pdf_text(file_bytes)

        return txns

    def _parse_row_heuristic(self, row) -> dict | None:
        """Try to parse a row without knowing column positions."""
        if not row or len(row) < 2:
            return None
        # First cell might be date
        date = self._parse_date(str(row[0] or ""))
        if not date:
            return None
        # Last cell is usually amount
        amt_str = str(row[-1] or "")
        amount = self._parse_amount(amt_str)
        if not amount:
            return None
        # Middle cells are description
        desc_parts = [str(c or "") for c in row[1:-1]]
        desc = self._clean_description(" ".join(desc_parts))
        if not desc:
            return None
        txn_type = "credit" if re.search(r"(Cr|CR)", amt_str) else "debit"
        return {"date": date, "description": desc, "amount": amount, "txn_type": txn_type}

    def _parse_pdf_text(self, file_bytes: bytes) -> List[Dict]:
        """Fallback text-based parsing for ICICI CC statements."""
        text = self._extract_pdf_text(file_bytes)
        txns = []
        # Pattern: DD/MM/YYYY Description Amount Dr/Cr
        pattern = re.compile(
            r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(Dr|Cr|DR|CR)?",
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
            dr_cr = (match.group(4) or "Dr").upper()
            txn_type = "credit" if dr_cr == "CR" else "debit"
            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})
        return txns

    def _parse_csv(self, file_bytes: bytes, filename: str) -> List[Dict]:
        """Fallback CSV parsing."""
        if self._is_excel(filename):
            df = self._read_excel(file_bytes)
        else:
            df = self._read_csv(file_bytes)

        df.columns = [c.strip().lower() for c in df.columns]
        txns = []

        date_col = next((c for c in df.columns if "date" in c), None)
        desc_col = next((c for c in df.columns if "description" in c or "particular" in c), None)
        amt_col = next((c for c in df.columns if "amount" in c), None)

        if not date_col or not desc_col or not amt_col:
            raise ValueError("Could not identify columns in ICICI CC statement")

        for _, row in df.iterrows():
            date = self._parse_date(str(row.get(date_col, "")))
            if not date:
                continue
            desc = self._clean_description(str(row.get(desc_col, "")))
            if not desc:
                continue
            amt_str = str(row.get(amt_col, ""))
            amount = self._parse_amount(amt_str)
            if not amount:
                continue
            txn_type = "credit" if re.search(r"(Cr|CR)", amt_str) else "debit"
            txns.append({"date": date, "description": desc, "amount": amount, "txn_type": txn_type})

        return txns
