---
name: grist-accounting
description: Use when working with the Grist double-entry accounting system - recording transactions, entering bills, tracking vendors, querying account balances, or generating financial reports
---

# Grist Double-Entry Accounting System

## Overview

A complete double-entry accounting system for sole proprietorship service businesses. Every transaction creates balanced journal entries (debits = credits). Account balances roll up through parent-child hierarchy.

## MCP Tools Available

| Tool | Purpose |
|------|---------|
| `mcp__grist-accounting__list_documents` | List accessible Grist documents |
| `mcp__grist-accounting__list_tables` | List tables in a document |
| `mcp__grist-accounting__describe_table` | Get column schema for a table |
| `mcp__grist-accounting__get_records` | Fetch records (with optional filter, sort, limit) |
| `mcp__grist-accounting__add_records` | Insert new records, returns `{"inserted_ids": [...]}` |
| `mcp__grist-accounting__update_records` | Update existing records by ID |
| `mcp__grist-accounting__delete_records` | Delete records by ID |
| `mcp__grist-accounting__sql_query` | Run read-only SQL queries |

The document name is `accounting` for all operations.

## Date Handling

All date fields use **Unix timestamps** (seconds since 1970-01-01 UTC).

| Date | Timestamp |
|------|-----------|
| Oct 1, 2025 | 1759363200 |
| Nov 1, 2025 | 1762041600 |
| Dec 1, 2025 | 1764633600 |
| Jan 1, 2026 | 1767312000 |

Python: `int(datetime(2025, 10, 1).timestamp())`

## Complete Table Schemas

### Accounts
| Column | Type | Notes |
|--------|------|-------|
| Code | Text | Account number (e.g., "5080") |
| Name | Text | Account name |
| Type | Choice | "Asset", "Liability", "Equity", "Income", "Expense" |
| Parent | Ref:Accounts | Parent account for hierarchy (0 = top-level) |
| Description | Text | |
| IsActive | Bool | |
| Balance | Formula | Calculated from transactions |

### Vendors
| Column | Type | Notes |
|--------|------|-------|
| Name | Text | Vendor name |
| DefaultExpenseAccount | Ref:Accounts | Auto-fills on bill lines |
| PaymentTerms | Choice | "Due on Receipt", "Net 15", "Net 30" |
| Notes | Text | |
| IsActive | Bool | |
| Balance | Formula | Sum of unpaid bills |

### Items
| Column | Type | Notes |
|--------|------|-------|
| Name | Text | Item name (e.g., "Software Subscription") |
| DefaultAccount | Ref:Accounts | Expense account for this item |
| DefaultDescription | Text | Auto-fills on bill lines |
| IsActive | Bool | |

### Bills
| Column | Type | Notes |
|--------|------|-------|
| Vendor | Ref:Vendors | Required |
| BillNumber | Text | Invoice number from vendor |
| BillDate | Date | Unix timestamp |
| DueDate | Date | Unix timestamp |
| Status | Choice | "Open", "Partial", "Paid" |
| Memo | Text | |
| EntryTransaction | Ref:Transactions | Link to journal entry |
| Invoice | Attachments | Vendor invoice document (use `["L", id]` format) |
| Receipt | Attachments | Payment receipt/confirmation (use `["L", id]` format) |
| Amount | Formula | Sum of BillLines.Amount |
| AmountPaid | Formula | Sum of BillPayments.Amount |
| AmountDue | Formula | Amount - AmountPaid |

### BillLines
| Column | Type | Notes |
|--------|------|-------|
| Bill | Ref:Bills | Required |
| Item | Ref:Items | Optional - auto-fills Account/Description |
| Account | Ref:Accounts | Expense account |
| Description | Text | |
| Amount | Numeric | Line item amount |

### Transactions
| Column | Type | Notes |
|--------|------|-------|
| Date | Date | Unix timestamp |
| Description | Text | Transaction description |
| Reference | Text | Check number, invoice reference, etc. |
| Status | Choice | "Draft", "Posted", "Cleared" |
| Memo | Text | |
| Total | Formula | Sum of debits |
| IsBalanced | Formula | True if debits = credits |

### TransactionLines
| Column | Type | Notes |
|--------|------|-------|
| Transaction | Ref:Transactions | Required |
| Account | Ref:Accounts | Required |
| Debit | Numeric | Debit amount (or 0) |
| Credit | Numeric | Credit amount (or 0) |
| Memo | Text | |

### BillPayments
| Column | Type | Notes |
|--------|------|-------|
| Bill | Ref:Bills | Required |
| Transaction | Ref:Transactions | Payment journal entry |
| Amount | Numeric | Payment amount |
| PaymentDate | Date | Unix timestamp |

## Key Account IDs

| ID | Code | Name | Type |
|----|------|------|------|
| 4 | 2000 | Accounts Payable | Liability |
| 14 | 1001 | Checking Account | Asset |
| 22 | 2203 | Due to Owner | Liability |
| 36 | 5080 | Software & Subscriptions | Expense |

Query all accounts:
```sql
SELECT id, Code, Name, Type FROM Accounts WHERE IsActive = true ORDER BY Code
```

## Account Types

| Type | Normal Balance | Increases With | Examples |
|------|----------------|----------------|----------|
| Asset | Debit | Debit | Cash, AR, Prepaid |
| Liability | Credit | Credit | AP, Credit Cards, Due to Owner |
| Equity | Credit | Credit | Owner's Investment, Draws, Retained Earnings |
| Income | Credit | Credit | Service Revenue, Interest Income |
| Expense | Debit | Debit | Rent, Utilities, Office Supplies |

## Complete Workflows

### Create a Vendor

```python
add_records("Vendors", [{
    "Name": "Acme Corp",
    "DefaultExpenseAccount": 36,  # Software & Subscriptions
    "PaymentTerms": "Due on Receipt",
    "Notes": "Software vendor",
    "IsActive": True
}])
# Returns: {"inserted_ids": [vendor_id]}
```

### Create Items for Common Purchases

```python
add_records("Items", [{
    "Name": "Monthly Software",
    "DefaultAccount": 36,
    "DefaultDescription": "Monthly SaaS subscription",
    "IsActive": True
}])
```

### Complete Bill Entry (5 Steps)

**Step 1: Create Bill Header**
```python
add_records("Bills", [{
    "Vendor": 1,  # vendor_id
    "BillNumber": "INV-001",
    "BillDate": 1759708800,  # Unix timestamp
    "DueDate": 1759708800,
    "Status": "Open",
    "Memo": "October services"
}])
# Returns: {"inserted_ids": [bill_id]}
```

**Step 2: Create Bill Line(s)**
```python
add_records("BillLines", [{
    "Bill": 1,  # bill_id from step 1
    "Item": 1,  # optional - auto-fills Account/Description
    "Account": 36,  # expense account
    "Description": "Monthly subscription",
    "Amount": 100.00
}])
```

**Step 3: Create Journal Entry**
```python
# Transaction header
add_records("Transactions", [{
    "Date": 1759708800,
    "Description": "Acme Corp - October services",
    "Reference": "INV-001",
    "Status": "Posted"
}])
# Returns: {"inserted_ids": [txn_id]}

# Transaction lines: Debit expense, Credit AP
add_records("TransactionLines", [
    {"Transaction": 1, "Account": 36, "Debit": 100.00, "Credit": 0, "Memo": "Monthly subscription"},
    {"Transaction": 1, "Account": 4, "Debit": 0, "Credit": 100.00, "Memo": "Monthly subscription"}
])
```

**Step 4: Link Bill to Transaction**
```python
update_records("Bills", [{"id": 1, "fields": {"EntryTransaction": 1}}])
```

**Step 5: Upload Invoice (if available)**

If an invoice PDF is available, upload and link it to the Invoice field:
```bash
# Get session token, then upload to Invoice field
bash /path/to/scripts/upload-attachment.sh invoice.pdf Bills 1 $TOKEN Invoice
```

Or for batch uploads, use a script (see Batch Operations).

### Pay Bill from Checking Account

```python
# Step 1: Create payment transaction
add_records("Transactions", [{
    "Date": 1760832000,
    "Description": "Payment - Acme Corp INV-001",
    "Reference": "Check #1001",
    "Status": "Cleared"
}])
# Returns: {"inserted_ids": [txn_id]}

# Step 2: Debit AP, Credit Checking
add_records("TransactionLines", [
    {"Transaction": 2, "Account": 4, "Debit": 100.00, "Credit": 0, "Memo": "Pay INV-001"},
    {"Transaction": 2, "Account": 14, "Debit": 0, "Credit": 100.00, "Memo": "Pay INV-001"}
])

# Step 3: Create BillPayment record
add_records("BillPayments", [{
    "Bill": 1,
    "Transaction": 2,
    "Amount": 100.00,
    "PaymentDate": 1760832000
}])

# Step 4: Update bill status
update_records("Bills", [{"id": 1, "fields": {"Status": "Paid"}}])

# Step 5: Upload receipt (if available)
bash /path/to/scripts/upload-attachment.sh receipt.pdf Bills 1 $TOKEN Receipt
```

### Pay Bill via Owner Reimbursement

When the owner pays a business expense personally:

```python
# Step 1: Create payment transaction
add_records("Transactions", [{
    "Date": 1760832000,
    "Description": "Owner payment - Acme Corp INV-001",
    "Reference": "Owner Reimb",
    "Status": "Posted"
}])

# Step 2: Debit AP, Credit Due to Owner (not Checking)
add_records("TransactionLines", [
    {"Transaction": 2, "Account": 4, "Debit": 100.00, "Credit": 0, "Memo": "Pay INV-001"},
    {"Transaction": 2, "Account": 22, "Debit": 0, "Credit": 100.00, "Memo": "Owner paid"}
])

# Step 3: Create BillPayment record
add_records("BillPayments", [{
    "Bill": 1,
    "Transaction": 2,
    "Amount": 100.00,
    "PaymentDate": 1760832000
}])

# Step 4: Update bill status
update_records("Bills", [{"id": 1, "fields": {"Status": "Paid"}}])

# Step 5: Upload receipt (if available)
bash /path/to/scripts/upload-attachment.sh receipt.pdf Bills 1 $TOKEN Receipt
```

### Reimburse Owner

When business pays back the owner:

```python
add_records("Transactions", [{
    "Date": 1762041600,
    "Description": "Owner reimbursement",
    "Reference": "Transfer",
    "Status": "Cleared"
}])

add_records("TransactionLines", [
    {"Transaction": 3, "Account": 22, "Debit": 500.00, "Credit": 0, "Memo": "Reimburse owner"},
    {"Transaction": 3, "Account": 14, "Debit": 0, "Credit": 500.00, "Memo": "Reimburse owner"}
])
```

## Batch Operations

When entering multiple bills efficiently:

1. **Create all Bills first** → collect inserted IDs
2. **Create all BillLines** referencing bill IDs
3. **Create all Transactions** → collect inserted IDs
4. **Create all TransactionLines** referencing transaction IDs
5. **Update all Bills** with EntryTransaction links in one call
6. (If paying) Create payment transactions, lines, and BillPayments
7. **Upload invoice attachments** if files are available

### Batch Attachment Uploads

When invoice files are available, upload them after bill entry:

1. Request session token with write permission (1 hour TTL for batch work)
2. Create a mapping of bill_id → invoice file path
3. Loop: upload each file, link to corresponding bill

```bash
# Example batch upload pattern for invoices
TOKEN=$(request_session_token with write permission)
for each (bill_id, invoice_path):
    curl -X POST -H "Authorization: Bearer $TOKEN" \
         -F "file=@$invoice_path" \
         https://grist-mcp.bballou.com/api/v1/attachments
    # Returns attachment_id
    update_records("Bills", [{"id": bill_id, "fields": {"Invoice": ["L", attachment_id]}}])

# For receipts (after payment):
    update_records("Bills", [{"id": bill_id, "fields": {"Receipt": ["L", attachment_id]}}])
```

Example batch update:
```python
update_records("Bills", [
    {"id": 1, "fields": {"EntryTransaction": 1}},
    {"id": 2, "fields": {"EntryTransaction": 2}},
    {"id": 3, "fields": {"EntryTransaction": 3}}
])
```

## Common Queries

### Unpaid Bills by Vendor
```sql
SELECT v.Name, b.BillNumber, b.BillDate, b.Amount, b.AmountDue
FROM Bills b
JOIN Vendors v ON b.Vendor = v.id
WHERE b.Status IN ('Open', 'Partial')
ORDER BY b.DueDate
```

### Bills Summary by Vendor
```sql
SELECT v.Name as Vendor, COUNT(b.id) as Bills, SUM(b.Amount) as Total, SUM(b.AmountDue) as Due
FROM Bills b
JOIN Vendors v ON b.Vendor = v.id
GROUP BY v.Name
ORDER BY Total DESC
```

### Account Balances (Non-Zero)
```sql
SELECT Code, Name, Type, Balance
FROM Accounts
WHERE Balance != 0
ORDER BY Code
```

### Owner Reimbursement Balance
```sql
SELECT Balance FROM Accounts WHERE Code = '2203'
```

### Expense Summary by Account
```sql
SELECT a.Code, a.Name, a.Balance
FROM Accounts a
WHERE a.Type = 'Expense' AND a.Balance != 0
ORDER BY a.Balance DESC
```

### Transaction History for Account
```sql
SELECT t.Date, t.Description, t.Reference, tl.Debit, tl.Credit
FROM TransactionLines tl
JOIN Transactions t ON tl.Transaction = t.id
WHERE tl.Account = 36
ORDER BY t.Date DESC
```

### Verify All Transactions Balance
```sql
SELECT id, Description, Total, IsBalanced
FROM Transactions
WHERE IsBalanced = false
```

## Financial Reports

### Balance Sheet

Shows Assets = Liabilities + Equity at a point in time.

**Important:** Parent accounts roll up child balances. Query only top-level parents (Parent = 0) to avoid double-counting.

```sql
-- Assets, Liabilities, Equity (top-level only)
SELECT Code, Name, Type, Balance
FROM Accounts
WHERE Type IN ('Asset', 'Liability', 'Equity')
  AND Parent = 0
ORDER BY Type, Code
```

```sql
-- Net Income (for Equity section)
-- Query leaf expense accounts only (no children)
SELECT
  COALESCE(SUM(CASE WHEN Type = 'Income' THEN Balance ELSE 0 END), 0) -
  COALESCE(SUM(CASE WHEN Type = 'Expense' THEN Balance ELSE 0 END), 0) as NetIncome
FROM Accounts
WHERE Type IN ('Income', 'Expense')
  AND id NOT IN (SELECT DISTINCT Parent FROM Accounts WHERE Parent != 0)
```

**Presentation:**
| **Assets** | |
|---|---:|
| Cash & Bank Accounts | $X.XX |
| Accounts Receivable | $X.XX |
| **Total Assets** | **$X.XX** |

| **Liabilities** | |
|---|---:|
| Accounts Payable | $X.XX |
| Due to Owner | $X.XX |
| **Total Liabilities** | **$X.XX** |

| **Equity** | |
|---|---:|
| Retained Earnings | $X.XX |
| Net Income (Loss) | $X.XX |
| **Total Equity** | **$X.XX** |

| **Total Liabilities + Equity** | **$X.XX** |

### Income Statement

Shows Revenue - Expenses = Net Income for a period.

```sql
-- All income and expense accounts (leaf accounts only)
SELECT Code, Name, Type, Balance
FROM Accounts
WHERE Type IN ('Income', 'Expense')
  AND Balance != 0
  AND id NOT IN (SELECT DISTINCT Parent FROM Accounts WHERE Parent != 0)
ORDER BY Type DESC, Code
```

**Presentation:**
| **Income** | |
|---|---:|
| Service Revenue | $X.XX |
| **Total Income** | **$X.XX** |

| **Expenses** | |
|---|---:|
| Software & Subscriptions | $X.XX |
| Professional Services | $X.XX |
| **Total Expenses** | **$X.XX** |

| **Net Income (Loss)** | **$X.XX** |

### Trial Balance

Lists all accounts with non-zero balances. Debits should equal Credits.

```sql
SELECT
  Code,
  Name,
  Type,
  CASE WHEN Type IN ('Asset', 'Expense') THEN Balance ELSE 0 END as Debit,
  CASE WHEN Type IN ('Liability', 'Equity', 'Income') THEN Balance ELSE 0 END as Credit
FROM Accounts
WHERE Balance != 0
  AND id NOT IN (SELECT DISTINCT Parent FROM Accounts WHERE Parent != 0)
ORDER BY Code
```

### Accounts Payable Aging

```sql
SELECT
  v.Name as Vendor,
  b.BillNumber,
  b.BillDate,
  b.DueDate,
  b.AmountDue,
  CASE
    WHEN b.DueDate >= strftime('%s', 'now') THEN 'Current'
    WHEN b.DueDate >= strftime('%s', 'now') - 2592000 THEN '1-30 Days'
    WHEN b.DueDate >= strftime('%s', 'now') - 5184000 THEN '31-60 Days'
    ELSE '60+ Days'
  END as Aging
FROM Bills b
JOIN Vendors v ON b.Vendor = v.id
WHERE b.Status IN ('Open', 'Partial')
ORDER BY b.DueDate
```

## Validation Checklist

After entering bills, verify:

- [ ] Total bills match expected: `SELECT SUM(Amount) FROM Bills`
- [ ] All transactions balanced: `SELECT * FROM Transactions WHERE IsBalanced = false`
- [ ] AP balance correct: `SELECT Balance FROM Accounts WHERE Code = '2000'`
- [ ] Expense accounts increased appropriately
- [ ] Vendor balances reflect unpaid bills
- [ ] Invoices attached: `SELECT id, BillNumber FROM Bills WHERE Invoice IS NULL`
- [ ] Receipts attached for paid bills: `SELECT id, BillNumber FROM Bills WHERE Status = 'Paid' AND Receipt IS NULL`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Transaction not balanced | Ensure SUM(Debit) = SUM(Credit) before saving |
| Wrong debit/credit direction | Assets/Expenses increase with debit; Liabilities/Equity/Income increase with credit |
| Posting to parent account | Post to leaf accounts (1001 Checking, not 1000 Cash) |
| Forgetting AP entry for bills | Bills need both the expense debit AND the AP credit |
| Missing EntryTransaction link | Always update Bill.EntryTransaction after creating journal entry |
| Bill status not updated | Manually set Status to "Paid" after full payment |
| Using string dates | Dates must be Unix timestamps (seconds), not strings |
| Missing invoice/receipt | Upload invoice after bill entry, receipt after payment |

## Uploading Attachments

Attachments (invoices, receipts) are uploaded via the HTTP proxy endpoint, not MCP tools. This is efficient for binary files.

### Workflow

1. **Request session token** with write permission via MCP
2. **Upload file** via `POST /api/v1/attachments` with multipart/form-data
3. **Link attachment** to record via `update_records`

### Upload Script

Use `scripts/upload-attachment.sh` in this skill directory:

```bash
# Get session token first (via MCP request_session_token tool)
# Then run:
bash scripts/upload-attachment.sh invoice.pdf Bills 13              # Invoice column (default)
bash scripts/upload-attachment.sh invoice.pdf Bills 13 $TOKEN       # With token
bash scripts/upload-attachment.sh receipt.pdf Bills 13 $TOKEN Receipt  # Receipt column

# Environment variable for custom endpoint:
GRIST_MCP_URL=https://custom.example.com bash scripts/upload-attachment.sh ...
```

Run `bash scripts/upload-attachment.sh` without arguments for full usage.

### Linking Attachments Manually

Grist attachment columns use format: `["L", attachment_id]`

```python
# Link invoice to bill
update_records("Bills", [{"id": 13, "fields": {"Invoice": ["L", 1]}}])

# Link receipt to bill (after payment)
update_records("Bills", [{"id": 13, "fields": {"Receipt": ["L", 2]}}])
```

## Formula Columns (Auto-Calculated)

| Table.Column | Description |
|--------------|-------------|
| Accounts.Balance | OwnBalance + ChildrenBalance |
| Transactions.IsBalanced | True if sum of debits = sum of credits |
| Transactions.Total | Sum of debit amounts |
| Bills.Amount | Sum of BillLines.Amount |
| Bills.AmountPaid | Sum of BillPayments.Amount |
| Bills.AmountDue | Amount - AmountPaid |
| Vendors.Balance | Sum of AmountDue for unpaid bills |
