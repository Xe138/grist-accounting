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
| 30 | 5020 | Bank & Merchant Fees |
| 36 | 5080 | Software & Subscriptions |
