---
name: grist-accounting
description: Use when working with the Grist double-entry accounting system - recording transactions, entering bills, tracking vendors, querying account balances, or generating financial reports
---

# Grist Double-Entry Accounting System

Double-entry accounting for sole proprietorship. Every transaction creates balanced journal entries (debits = credits).

## Quick Reference

| Task | Action |
|------|--------|
| Record vendor invoice | Use template from `templates/`, then audit |
| Record payment | Use template from `templates/`, then audit |
| Reconcile bank account | See [reconciliation.md](references/reconciliation.md) |
| Query balances | Use `sql_query` on Accounts table |
| Generate reports | See [queries.md](references/queries.md) |

## Transaction Templates

**Always use templates** when creating transactions to avoid errors with formula fields.

| Scenario | Template |
|----------|----------|
| Invoice paid by credit card | [bill-paid-credit-card.json](templates/bill-paid-credit-card.json) |
| Invoice paid by owner | [bill-paid-owner.json](templates/bill-paid-owner.json) |
| Invoice paid from checking | [bill-paid-checking.json](templates/bill-paid-checking.json) |
| Invoice not yet paid | [bill-unpaid.json](templates/bill-unpaid.json) |
| Pay existing bill | [pay-existing-bill.json](templates/pay-existing-bill.json) |
| Direct expense (no bill) | [direct-expense.json](templates/direct-expense.json) |
| Bank import - deposit | [bank-import-deposit.json](templates/bank-import-deposit.json) |
| Bank import - withdrawal | [bank-import-expense.json](templates/bank-import-expense.json) |

Templates contain only writable fields. See [templates.md](references/templates.md) for usage guide.

## Recording Transactions: Decision Guide

| Source Document | What to Create |
|-----------------|----------------|
| **Invoice/Bill from vendor** | Bill + BillLines + Transaction + TransactionLines |
| **Receipt showing payment** | BillPayment + attach Receipt to existing Bill |
| **Bank statement entry** | Transaction + TransactionLines only |
| **Bank export file** | Run bank reconciliation workflow (see below) |
| **Journal adjustment** | Transaction + TransactionLines only |

**Key Rule:** If there's a vendor invoice number, always create a Bill record.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `list_documents` | List accessible Grist documents |
| `list_tables` | List tables in a document |
| `describe_table` | Get column schema |
| `get_records` | Fetch records (filter, sort, limit) |
| `add_records` | Insert records, returns `{"inserted_ids": [...]}` |
| `update_records` | Update by ID |
| `delete_records` | Delete by ID |
| `sql_query` | Read-only SQL |

Document name: `accounting`

## Date Handling

All dates use **Unix timestamps** (seconds since epoch).

| Date | Timestamp |
|------|-----------|
| Oct 1, 2025 | 1759363200 |
| Nov 1, 2025 | 1762041600 |
| Dec 1, 2025 | 1764633600 |
| Jan 1, 2026 | 1767312000 |

## Key Account IDs

| ID | Code | Name | Type |
|----|------|------|------|
| 4 | 2000 | Accounts Payable | Liability |
| 14 | 1001 | Checking Account | Asset |
| 22 | 2203 | Due to Owner | Liability |
| 36 | 5080 | Software & Subscriptions | Expense |

Query all: `SELECT id, Code, Name, Type FROM Accounts WHERE IsActive = true ORDER BY Code`

## Account Types

| Type | Normal Balance | Increases With |
|------|----------------|----------------|
| Asset | Debit | Debit |
| Liability | Credit | Credit |
| Equity | Credit | Credit |
| Income | Credit | Credit |
| Expense | Debit | Debit |

## Bill Entry Workflow (6 Steps)

1. Create Bill header with Vendor, BillNumber, BillDate, DueDate, Status="Open"
2. Create BillLine(s) with expense Account and Amount
3. Create Transaction + TransactionLines (Dr Expense, Cr AP)
4. Link Bill.EntryTransaction to transaction ID
5. Upload Invoice attachment if available
6. **Run post-entry audit (REQUIRED)**

For detailed code: see [workflows.md](references/workflows.md)

## Payment Workflows

**Pay from Checking:**
1. Create Transaction (Dr AP, Cr Checking)
2. Create BillPayment record
3. Update Bill.Status = "Paid"
4. Upload Receipt if available
5. **Run post-payment audit**

**Owner pays personally:**
Same as above but Cr Due to Owner (id=22) instead of Checking

For detailed code: see [workflows.md](references/workflows.md)

## Bank Reconciliation Workflow (4 Phases)

Import bank transactions, match against ledger, create missing entries, and verify balances.

**Phase 1 — Import:** Read bank export file (Schwab JSON), parse dates/amounts, present summary
**Phase 2 — Match:** Fetch TransactionLines for bank account via `get_records`, match by amount + date (±3 days)
**Phase 3 — Create:** For unmatched bank entries, check BankRules, suggest offset account by Type, create Transaction + TransactionLines (Status="Cleared")
**Phase 4 — Reconcile:** Create Reconciliation record, calculate cleared balance, compare to statement balance

For detailed reference: see [reconciliation.md](references/reconciliation.md)
For workflow code examples: see [workflows.md](references/workflows.md)

## Validation Checklist

After entering bills:
- [ ] `SELECT * FROM Transactions WHERE IsBalanced = false` returns empty
- [ ] `SELECT Balance FROM Accounts WHERE Code = '2000'` shows correct AP
- [ ] `SELECT id, BillNumber FROM Bills WHERE Invoice IS NULL` - upload missing

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Writing to formula columns | Use templates - they only include writable fields |
| Transaction not balanced | Ensure SUM(Debit) = SUM(Credit) |
| Wrong debit/credit direction | Assets/Expenses: debit increases; Liabilities/Equity/Income: credit increases |
| Posting to parent account | Post to leaf accounts (1001 not 1000) |
| Missing EntryTransaction link | Always link Bill to Transaction |
| Using string dates | Use Unix timestamps |
| SQL error on TransactionLines | Column `Transaction` is reserved; use `get_records` with filter |

**Formula Columns (read-only):** Bills.Amount, Bills.AmountPaid, Bills.AmountDue, Transactions.Total, Transactions.IsBalanced

## Uploading Attachments

```bash
# Get session token, then:
bash scripts/upload-attachment.sh invoice.pdf Bills {id} $TOKEN Invoice
bash scripts/upload-attachment.sh receipt.pdf Bills {id} $TOKEN Receipt
```

## Audit Subagent

**REQUIRED:** Run audit checks after every bill entry before considering complete.

### Behavior

Claude MUST run post-entry audit checks. The audit:
1. Executes independently from entry workflow
2. Validates all aspects of newly created records
3. Reports findings in structured format
4. Does not auto-correct - alerts user to take action

### Audit Categories

| Category | Severity | Description |
|----------|----------|-------------|
| Transaction Balance | Critical | Debits must equal credits |
| Account Usage | Error | Correct account types |
| Bill Linkage | Error | EntryTransaction and Vendor set |
| Amount Match | Error | Bill.Amount matches transaction |
| PDF Verification | Warning | Document values match database |
| Missing Attachments | Warning | Invoice/Receipt attached |

### Quick Audit

```sql
-- Check transaction balanced
SELECT IsBalanced FROM Transactions WHERE id = {txn_id}

-- Check bill integrity
SELECT id, Vendor, EntryTransaction, Amount FROM Bills WHERE id = {bill_id}
```

### Output Format

| Check | Status | Details |
|-------|--------|---------|
| Transaction Balanced | PASS/FAIL | ... |
| Bill Integrity | PASS/FAIL | ... |
| PDF Verification | PASS/WARN/SKIP | ... |

For full audit queries and remediation: see [audit.md](references/audit.md)

## Reference Files

| File | Contents |
|------|----------|
| [references/templates.md](references/templates.md) | Template usage guide |
| [references/schema.md](references/schema.md) | Complete table schemas |
| [references/workflows.md](references/workflows.md) | Detailed code examples |
| [references/queries.md](references/queries.md) | SQL queries and financial reports |
| [references/audit.md](references/audit.md) | Audit queries and remediation |
| [references/reconciliation.md](references/reconciliation.md) | Bank reconciliation workflow |
