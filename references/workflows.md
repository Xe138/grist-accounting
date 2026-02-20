# Workflow Examples

Detailed code examples for common accounting operations.

**Important:** Before adding records, consult [schema.md](schema.md) to identify writable fields. Formula columns (marked "Formula" in schema) must NOT be included in `add_records` payloads or a 400 error will occur.

## Contents
- [Create a Vendor](#create-a-vendor)
- [Create Items](#create-items-for-common-purchases)
- [Complete Bill Entry](#complete-bill-entry-6-steps)
- [Pay Bill from Checking](#pay-bill-from-checking-account)
- [Pay Bill via Owner](#pay-bill-via-owner-reimbursement)
- [Reimburse Owner](#reimburse-owner)
- [Batch Operations](#batch-operations)
- [Bank Reconciliation](#bank-reconciliation)

## Create a Vendor

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

## Create Items for Common Purchases

```python
add_records("Items", [{
    "Name": "Monthly Software",
    "DefaultAccount": 36,
    "DefaultDescription": "Monthly SaaS subscription",
    "IsActive": True
}])
```

## Complete Bill Entry (6 Steps)

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
```bash
bash scripts/upload-attachment.sh invoice.pdf Bills 1 $TOKEN Invoice
```

**Step 6: Post-Entry Audit (REQUIRED)**

Run audit checks before concluding. See [Audit Reference](audit.md) for details.

```sql
-- Check 1: Transaction balanced
SELECT IsBalanced FROM Transactions WHERE id = {txn_id}
-- Expected: true

-- Check 2: Bill integrity
SELECT id, Vendor, EntryTransaction, Amount FROM Bills WHERE id = {bill_id}
-- Expected: All fields populated, Amount > 0
```

## Pay Bill from Checking Account

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
# bash scripts/upload-attachment.sh receipt.pdf Bills 1 $TOKEN Receipt

# Step 6: Post-Payment Audit (REQUIRED)
# Verify payment transaction balances and bill status updated correctly
```

## Pay Bill via Owner Reimbursement

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
# bash scripts/upload-attachment.sh receipt.pdf Bills 1 $TOKEN Receipt

# Step 6: Post-Payment Audit (REQUIRED)
```

## Reimburse Owner

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

```bash
# Example batch upload pattern
TOKEN=$(request_session_token with write permission)
for each (bill_id, invoice_path):
    curl -X POST -H "Authorization: Bearer $TOKEN" \
         -F "file=@$invoice_path" \
         https://grist-mcp.bballou.com/api/v1/attachments
    # Returns attachment_id
    update_records("Bills", [{"id": bill_id, "fields": {"Invoice": ["L", attachment_id]}}])
```

### Batch Update Example

```python
update_records("Bills", [
    {"id": 1, "fields": {"EntryTransaction": 1}},
    {"id": 2, "fields": {"EntryTransaction": 2}},
    {"id": 3, "fields": {"EntryTransaction": 3}}
])
```

## Sample Payloads

Copy-paste ready JSON payloads for `add_records`. Only writable fields are included.

### Owner Equity Contribution

```json
// Transaction
{"Date": 1768348800, "Description": "Owner equity contribution", "Reference": "Owner Investment", "Status": "Posted", "Memo": ""}

// TransactionLines (Debit Checking, Credit Owner's Investment)
[
  {"Transaction": 51, "Account": 14, "Debit": 1000, "Credit": 0, "Memo": "Owner equity contribution"},
  {"Transaction": 51, "Account": 23, "Debit": 0, "Credit": 1000, "Memo": "Owner equity contribution"}
]
```

### Owner Draw

```json
// Transaction
{"Date": 1768348800, "Description": "Owner draw", "Reference": "Transfer", "Status": "Cleared", "Memo": ""}

// TransactionLines (Debit Owner's Draws, Credit Checking)
[
  {"Transaction": 52, "Account": 24, "Debit": 500, "Credit": 0, "Memo": "Owner draw"},
  {"Transaction": 52, "Account": 14, "Debit": 0, "Credit": 500, "Memo": "Owner draw"}
]
```

### Direct Expense (No Bill)

For bank fees, minor expenses without vendor invoices:

```json
// Transaction
{"Date": 1768348800, "Description": "Bank service fee", "Reference": "Statement", "Status": "Cleared", "Memo": "Monthly account fee"}

// TransactionLines (Debit Expense, Credit Checking)
[
  {"Transaction": 53, "Account": 30, "Debit": 15, "Credit": 0, "Memo": "Monthly fee"},
  {"Transaction": 53, "Account": 14, "Debit": 0, "Credit": 15, "Memo": "Monthly fee"}
]
```

### Revenue Receipt

```json
// Transaction
{"Date": 1768348800, "Description": "Client payment - Project X", "Reference": "INV-100", "Status": "Cleared", "Memo": ""}

// TransactionLines (Debit Checking, Credit Revenue)
[
  {"Transaction": 54, "Account": 14, "Debit": 2500, "Credit": 0, "Memo": "Project X payment"},
  {"Transaction": 54, "Account": 25, "Debit": 0, "Credit": 2500, "Memo": "Service revenue"}
]
```

### Key Account IDs Reference

| ID | Code | Name |
|----|------|------|
| 4 | 2000 | Accounts Payable |
| 14 | 1001 | Checking Account |
| 22 | 2203 | Due to Owner |
| 23 | 3001 | Owner's Investment |
| 24 | 3002 | Owner's Draws |
| 25 | 4001 | Service Revenue |
| 26 | 4010 | Interest Income |
| 30 | 5020 | Bank & Merchant Fees |
| 36 | 5080 | Software & Subscriptions |

## Bank Reconciliation

Import bank transactions, match against ledger, create missing entries, and reconcile.

For full reference: see [reconciliation.md](reconciliation.md)

### Phase 1: Import Bank File (Schwab JSON)

```python
# Read and parse the bank export file
import json
with open("path/to/schwab_export.json") as f:
    data = json.load(f)

# Parse each PostedTransaction
for txn in data["PostedTransactions"]:
    # Date: "MM/DD/YYYY" -> Unix timestamp
    # Amount: parse "$X,XXX.XX" strings; Deposit = positive, Withdrawal = negative
    # Empty string = no amount (skip)
    pass
```

### Phase 2: Match Against Ledger

```python
# Fetch existing TransactionLines for Checking (id=14)
# MUST use get_records, not sql_query (Transaction is reserved word)
get_records("TransactionLines", filter={"Account": [14]})

# Get transaction details for date matching
sql_query("SELECT id, Date, Description, Status FROM Transactions WHERE id IN (...)")

# Match criteria: exact amount AND date ±3 days AND not already matched
# Deposits match Debit > 0 (money into checking = debit to asset)
# Withdrawals match Credit > 0 (money out of checking = credit to asset)
```

### Phase 3: Create Missing Transactions

```python
# For unmatched deposits (e.g., interest income):
add_records("Transactions", [{
    "Date": 1738195200,
    "Description": "Bank interest income",
    "Reference": "Interest Paid",
    "Status": "Cleared",
    "Memo": "Auto-imported from bank statement"
}])
# Returns: {"inserted_ids": [txn_id]}

# Dr Checking, Cr Interest Income
add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": 14, "Debit": 0.01, "Credit": 0, "Memo": "Bank interest"},
    {"Transaction": txn_id, "Account": 26, "Debit": 0, "Credit": 0.01, "Memo": "Bank interest"}
])

# For unmatched withdrawals (e.g., ATM owner draw):
add_records("Transactions", [{
    "Date": 1739750400,
    "Description": "ATM withdrawal - owner draw",
    "Reference": "P421164 88 ESSEX STREET NEW YORK",
    "Status": "Cleared",
    "Memo": "Auto-imported from bank statement"
}])

# Dr Owner's Draws, Cr Checking
add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": 24, "Debit": 102.00, "Credit": 0, "Memo": "ATM withdrawal"},
    {"Transaction": txn_id, "Account": 14, "Debit": 0, "Credit": 102.00, "Memo": "ATM withdrawal"}
])

# Optionally save a BankRule for auto-categorization:
add_records("BankRules", [{
    "Account": 14,
    "Pattern": "Interest Paid",
    "MatchType": "Contains",
    "OffsetAccount": 26,
    "TransactionDescription": "Bank interest income",
    "IsActive": true
}])
```

### Phase 4: Reconcile

```python
# Update matched existing transactions to Cleared status
update_records("Transactions", [
    {"id": existing_txn_id, "fields": {"Status": "Cleared"}}
])

# Calculate cleared balance
lines = get_records("TransactionLines", filter={"Account": [14]})
txn_ids = list(set(l["fields"]["Transaction"] for l in lines))
cleared = sql_query(f"SELECT id FROM Transactions WHERE Status = 'Cleared' AND id IN (...)")
cleared_ids = set(r["id"] for r in cleared)
cleared_balance = sum(
    l["fields"]["Debit"] - l["fields"]["Credit"]
    for l in lines
    if l["fields"]["Transaction"] in cleared_ids
)

# Create Reconciliation record
add_records("Reconciliations", [{
    "Account": 14,
    "StatementDate": 1739750400,  # date of last bank entry
    "StatementBalance": 1398.01,
    "ClearedBalance": cleared_balance,
    "Difference": 1398.01 - cleared_balance,
    "Status": "Completed",  # if Difference == 0
    "StartedAt": 1739923200,  # today
    "CompletedAt": 1739923200,
    "Notes": "Reconciled against Schwab export"
}])

# Verify
sql_query("SELECT * FROM Transactions WHERE IsBalanced = false")
```
