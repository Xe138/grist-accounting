# Audit Reference

Detailed audit queries, workflows, and remediation steps.

## Contents
- [Audit SQL Queries](#audit-sql-queries)
- [PDF Verification Workflow](#pdf-verification-workflow)
- [Post-Entry Audit Checklist](#post-entry-audit-checklist)
- [Output Formats](#output-formats)
- [Remediation Steps](#remediation-steps)

## Audit SQL Queries

### Check 1: Unbalanced Transactions
```sql
-- Simple check using formula column
SELECT id, Date, Description, IsBalanced FROM Transactions WHERE IsBalanced = 0

-- Detailed check with actual sums (for debugging)
SELECT t.id, t.Description,
       (SELECT SUM(Debit) FROM TransactionLines WHERE Transaction = t.id) as TotalDebit,
       (SELECT SUM(Credit) FROM TransactionLines WHERE Transaction = t.id) as TotalCredit
FROM Transactions t
WHERE t.IsBalanced = 0
```

### Check 2: Invalid Account Usage

Detect debits to non-debit-normal accounts or credits to non-credit-normal accounts:
```sql
SELECT t.id, t.Description, tl.id as LineId, a.Name, a.Type,
       tl.Debit, tl.Credit
FROM TransactionLines tl
JOIN Transactions t ON tl.Transaction = t.id
JOIN Accounts a ON tl.Account = a.id
WHERE (tl.Debit > 0 AND a.Type NOT IN ('Asset', 'Expense'))
   OR (tl.Credit > 0 AND a.Type NOT IN ('Liability', 'Equity', 'Income'))
```

Note: This query flags unusual patterns. Some are valid (e.g., paying down AP debits a Liability). Review flagged items manually.

### Check 3: Bills Missing Required Links
```sql
SELECT b.id, b.BillNumber, b.Status, b.EntryTransaction, b.Vendor
FROM Bills b
WHERE b.EntryTransaction IS NULL
   OR b.Vendor IS NULL
```

### Check 4: Bill/Transaction Amount Mismatch
```sql
SELECT b.id, b.BillNumber, b.Amount as BillAmount,
       (SELECT SUM(tl.Debit) FROM TransactionLines tl
        JOIN Accounts a ON tl.Account = a.id
        WHERE tl.Transaction = b.EntryTransaction AND a.Type = 'Expense') as TxnExpense
FROM Bills b
WHERE b.EntryTransaction IS NOT NULL
  AND b.Amount != (SELECT SUM(tl.Debit) FROM TransactionLines tl
                   JOIN Accounts a ON tl.Account = a.id
                   WHERE tl.Transaction = b.EntryTransaction AND a.Type = 'Expense')
```

### Check 5: Paid Bills Without BillPayments
```sql
SELECT b.id, b.BillNumber, b.Amount, b.AmountPaid, b.Status
FROM Bills b
WHERE b.Status = 'Paid' AND (b.AmountPaid IS NULL OR b.AmountPaid = 0)
```

### Check 6: Bills Missing Attachments
```sql
SELECT b.id, b.BillNumber, b.Invoice, b.Receipt, b.Status
FROM Bills b
WHERE b.Invoice IS NULL
   OR (b.Status = 'Paid' AND b.Receipt IS NULL)
```

## PDF Verification Workflow

When an invoice attachment exists, verify its contents match the bill record:

1. **Download attachment**
   ```bash
   bash scripts/download-attachment.sh <attachment_id> /tmp/invoice.pdf $TOKEN
   ```

2. **Extract invoice data**
   ```bash
   python scripts/verify-pdf.py /tmp/invoice.pdf --json
   ```

3. **Compare extracted values**
   - Invoice number vs Bill.BillNumber
   - Date vs Bill.BillDate (allow 1 day tolerance)
   - Amount vs Bill.Amount (must match within $0.01)
   - Vendor name vs Vendors.Name (fuzzy match)

4. **Report discrepancies** with severity levels

## Post-Entry Audit Checklist

After completing a bill entry, run these checks on the newly created records:

**Step 1: Transaction Balance**
```sql
SELECT IsBalanced FROM Transactions WHERE id = {txn_id}
```
Expected: `true`

**Step 2: Account Usage**
Verify the transaction lines use correct accounts:
- Expense account (Type = 'Expense') for the debit
- AP account (id=4, code 2000) for the credit

**Step 3: Bill Integrity**
```sql
SELECT id, Vendor, EntryTransaction, Amount
FROM Bills WHERE id = {bill_id}
```
Expected: All fields populated, Amount > 0

**Step 4: PDF Verification** (if Invoice attachment exists)
Run the PDF verification workflow above.

## Output Formats

### Single Entry Audit
| Check | Status | Details |
|-------|--------|---------|
| Transaction Balanced | PASS | Debits = Credits = $X.XX |
| Account Usage | PASS | Expense: 5080, AP: 2000 |
| Bill Integrity | PASS | All required fields set |
| PDF Verification | WARN | Date mismatch: PDF shows 10/5, Bill has 10/6 |

### Full Audit Report
| Category | Severity | Count | Details |
|----------|----------|-------|---------|
| Unbalanced Transactions | Critical | 0 | None |
| Account Misuse | Warning | 2 | Txn #5, #12 |
| Missing Bill Links | Error | 1 | Bill #123 |
| Amount Mismatches | Error | 0 | None |
| PDF Discrepancies | Warning | 3 | Bills #1, #2, #5 |
| Missing Attachments | Warning | 5 | Bills #3, #4, #6, #7, #8 |

### Severity Levels
- **PASS**: Check passed
- **WARN**: Minor discrepancy, review recommended
- **ERROR**: Significant issue, correction required
- **CRITICAL**: Data integrity problem, must fix immediately

## Remediation Steps

| Issue | Remediation |
|-------|-------------|
| Unbalanced transaction | Review TransactionLines, add/adjust lines until SUM(Debit) = SUM(Credit) |
| Wrong account type | Update TransactionLine.Account to correct account |
| Missing EntryTransaction | Link bill to transaction: `update_records("Bills", [{"id": X, "fields": {"EntryTransaction": Y}}])` |
| Missing Vendor | Set Bill.Vendor to appropriate vendor ID |
| Amount mismatch | Review bill lines and transaction lines, correct the discrepancy |
| PDF mismatch | Verify source document, update bill fields if database is wrong |
| Missing attachment | Upload invoice/receipt using `scripts/upload-attachment.sh` |
