#!/usr/bin/env python3
"""
verify-pdf.py - Extract and verify invoice data from PDF files

Usage:
    python verify-pdf.py <pdf_file> [--bill-id N] [--json]

Examples:
    python verify-pdf.py invoice.pdf
    python verify-pdf.py invoice.pdf --bill-id 1
    python verify-pdf.py invoice.pdf --json

Dependencies:
    pip install pdfplumber pytesseract pillow pdf2image python-dateutil

System packages (for OCR):
    tesseract-ocr poppler-utils
"""

import argparse
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# PDF extraction
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# OCR fallback
try:
    import pytesseract
    from pdf2image import convert_from_path
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# Date parsing
try:
    from dateutil import parser as dateparser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


def extract_text_pdfplumber(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber (fast, text-based PDFs)."""
    if not HAS_PDFPLUMBER:
        return ""

    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        print(f"pdfplumber error: {e}", file=sys.stderr)
        return ""

    return "\n".join(text_parts)


def extract_text_ocr(pdf_path: str) -> str:
    """Extract text from PDF using OCR (slower, handles scanned documents)."""
    if not HAS_OCR:
        return ""

    text_parts = []
    try:
        images = convert_from_path(pdf_path, dpi=200)
        for i, image in enumerate(images):
            page_text = pytesseract.image_to_string(image)
            if page_text:
                text_parts.append(page_text)
    except Exception as e:
        print(f"OCR error: {e}", file=sys.stderr)
        return ""

    return "\n".join(text_parts)


def extract_text(pdf_path: str) -> tuple[str, str]:
    """
    Extract text from PDF with OCR fallback.
    Returns (text, method) where method is 'pdfplumber', 'ocr', or 'none'.
    """
    # Try text extraction first (fast)
    text = extract_text_pdfplumber(pdf_path)
    if len(text.strip()) >= 50:
        return text, "pdfplumber"

    # Fall back to OCR for scanned documents
    text = extract_text_ocr(pdf_path)
    if text.strip():
        return text, "ocr"

    return "", "none"


def parse_invoice_number(text: str) -> str | None:
    """Extract invoice number from text."""
    patterns = [
        r'(?:Invoice|Inv|Invoice\s*#|Invoice\s*Number|Invoice\s*No\.?)[:\s]*([A-Z0-9][-A-Z0-9]{3,})',
        r'(?:Order|Order\s*#|Order\s*Number)[:\s]*([A-Z0-9][-A-Z0-9]{3,})',
        r'(?:Reference|Ref|Ref\s*#)[:\s]*([A-Z0-9][-A-Z0-9]{3,})',
        r'#\s*([A-Z0-9][-A-Z0-9]{5,})',  # Generic # followed by alphanumeric
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def parse_date(text: str) -> tuple[str | None, int | None]:
    """
    Extract date from text.
    Returns (date_string, unix_timestamp) or (None, None).
    """
    if not HAS_DATEUTIL:
        return None, None

    # Look for labeled dates first
    date_patterns = [
        r'(?:Invoice\s*Date|Date|Issued)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(?:Invoice\s*Date|Date|Issued)[:\s]*(\w+\s+\d{1,2},?\s+\d{4})',
        r'(?:Invoice\s*Date|Date|Issued)[:\s]*(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            try:
                parsed = dateparser.parse(date_str)
                if parsed:
                    return date_str, int(parsed.timestamp())
            except:
                pass

    # Try to find any date-like pattern
    generic_patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
        r'(\w+\s+\d{1,2},?\s+\d{4})',
    ]

    for pattern in generic_patterns:
        matches = re.findall(pattern, text)
        for date_str in matches[:3]:  # Check first 3 matches
            try:
                parsed = dateparser.parse(date_str)
                if parsed and 2020 <= parsed.year <= 2030:
                    return date_str, int(parsed.timestamp())
            except:
                pass

    return None, None


def parse_amount(text: str) -> tuple[str | None, Decimal | None]:
    """
    Extract total amount from text.
    Returns (amount_string, decimal_value) or (None, None).
    """
    # Look for labeled totals (prioritize these)
    total_patterns = [
        r'(?:Total|Amount\s*Due|Grand\s*Total|Balance\s*Due|Total\s*Due)[:\s]*\$?([\d,]+\.?\d*)',
        r'(?:Total|Amount\s*Due|Grand\s*Total|Balance\s*Due|Total\s*Due)[:\s]*USD?\s*([\d,]+\.?\d*)',
    ]

    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return match.group(1), Decimal(amount_str)
            except InvalidOperation:
                pass

    # Look for currency amounts (less reliable)
    currency_pattern = r'\$\s*([\d,]+\.\d{2})'
    matches = re.findall(currency_pattern, text)
    if matches:
        # Return the largest amount found (likely the total)
        amounts = []
        for m in matches:
            try:
                amounts.append((m, Decimal(m.replace(',', ''))))
            except:
                pass
        if amounts:
            amounts.sort(key=lambda x: x[1], reverse=True)
            return amounts[0]

    return None, None


def parse_vendor(text: str) -> str | None:
    """
    Extract vendor name from text.
    Usually appears in the header/letterhead area.
    """
    lines = text.split('\n')[:10]  # Check first 10 lines

    # Filter out common non-vendor lines
    skip_patterns = [
        r'^invoice',
        r'^date',
        r'^bill\s*to',
        r'^ship\s*to',
        r'^\d',
        r'^page',
        r'^total',
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 100:
            continue

        # Skip lines matching patterns
        skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break

        if skip:
            continue

        # Return first substantial line (likely company name)
        if re.match(r'^[A-Z]', line) and len(line) >= 3:
            return line

    return None


def extract_invoice_data(pdf_path: str) -> dict:
    """Extract all invoice data from a PDF file."""
    result = {
        'file': pdf_path,
        'extraction_method': None,
        'invoice_number': None,
        'date_string': None,
        'date_timestamp': None,
        'amount_string': None,
        'amount_decimal': None,
        'vendor': None,
        'raw_text_preview': None,
        'errors': [],
    }

    # Check file exists
    if not Path(pdf_path).exists():
        result['errors'].append(f"File not found: {pdf_path}")
        return result

    # Extract text
    text, method = extract_text(pdf_path)
    result['extraction_method'] = method
    result['raw_text_preview'] = text[:500] if text else None

    if not text:
        result['errors'].append("Could not extract text from PDF")
        return result

    # Parse fields
    result['invoice_number'] = parse_invoice_number(text)
    result['date_string'], result['date_timestamp'] = parse_date(text)
    result['amount_string'], amount = parse_amount(text)
    result['amount_decimal'] = float(amount) if amount else None
    result['vendor'] = parse_vendor(text)

    return result


def compare_with_bill(extracted: dict, bill: dict) -> list[dict]:
    """
    Compare extracted PDF data with bill record.
    Returns list of discrepancies.
    """
    issues = []

    # Compare invoice number
    if extracted.get('invoice_number') and bill.get('BillNumber'):
        if extracted['invoice_number'].upper() != bill['BillNumber'].upper():
            issues.append({
                'field': 'invoice_number',
                'severity': 'WARNING',
                'pdf_value': extracted['invoice_number'],
                'bill_value': bill['BillNumber'],
                'message': f"Invoice number mismatch: PDF has '{extracted['invoice_number']}', bill has '{bill['BillNumber']}'"
            })

    # Compare amount
    if extracted.get('amount_decimal') and bill.get('Amount'):
        pdf_amount = Decimal(str(extracted['amount_decimal']))
        bill_amount = Decimal(str(bill['Amount']))
        if abs(pdf_amount - bill_amount) > Decimal('0.01'):
            issues.append({
                'field': 'amount',
                'severity': 'ERROR',
                'pdf_value': float(pdf_amount),
                'bill_value': float(bill_amount),
                'message': f"Amount mismatch: PDF has ${pdf_amount}, bill has ${bill_amount}"
            })

    # Compare date (allow 1 day tolerance)
    if extracted.get('date_timestamp') and bill.get('BillDate'):
        pdf_ts = extracted['date_timestamp']
        bill_ts = bill['BillDate']
        diff_days = abs(pdf_ts - bill_ts) / 86400
        if diff_days > 1:
            issues.append({
                'field': 'date',
                'severity': 'WARNING',
                'pdf_value': extracted['date_string'],
                'bill_value': datetime.fromtimestamp(bill_ts).strftime('%Y-%m-%d'),
                'message': f"Date mismatch: PDF has '{extracted['date_string']}', bill has {datetime.fromtimestamp(bill_ts).strftime('%Y-%m-%d')}"
            })

    return issues


def main():
    parser = argparse.ArgumentParser(description='Extract and verify invoice data from PDF')
    parser.add_argument('pdf_file', help='Path to the PDF file')
    parser.add_argument('--bill-id', type=int, help='Bill ID to compare against (for future use)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    # Check dependencies
    missing = []
    if not HAS_PDFPLUMBER:
        missing.append('pdfplumber')
    if not HAS_DATEUTIL:
        missing.append('python-dateutil')

    if missing:
        print(f"Warning: Missing packages: {', '.join(missing)}", file=sys.stderr)
        print("Install with: pip install " + ' '.join(missing), file=sys.stderr)

    if not HAS_OCR:
        print("Note: OCR support unavailable (install pytesseract, pdf2image)", file=sys.stderr)

    # Extract data
    result = extract_invoice_data(args.pdf_file)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"File: {result['file']}")
        print(f"Extraction method: {result['extraction_method']}")
        print(f"Invoice #: {result['invoice_number'] or 'NOT FOUND'}")
        print(f"Date: {result['date_string'] or 'NOT FOUND'}")
        print(f"Amount: ${result['amount_decimal']:.2f}" if result['amount_decimal'] else "Amount: NOT FOUND")
        print(f"Vendor: {result['vendor'] or 'NOT FOUND'}")

        if result['errors']:
            print("\nErrors:")
            for err in result['errors']:
                print(f"  - {err}")

        if result['raw_text_preview']:
            print(f"\nText preview:\n{'-' * 40}")
            print(result['raw_text_preview'][:300])


if __name__ == '__main__':
    main()
