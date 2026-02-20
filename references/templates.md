# Transaction Templates

JSON templates for common accounting scenarios. Templates contain only **writable fields** to prevent errors when creating records.

## Template Selection Guide

| Scenario | Template |
|----------|----------|
| Vendor invoice paid by business credit card | `bill-paid-credit-card.json` |
| Vendor invoice paid by owner personally | `bill-paid-owner.json` |
| Vendor invoice paid from checking account | `bill-paid-checking.json` |
| Vendor invoice received but not yet paid | `bill-unpaid.json` |
| Recording payment for previously entered bill | `pay-existing-bill.json` |
| Bank fees, minor expenses without invoices | `direct-expense.json` |
| Bank import — unmatched deposit | `bank-import-deposit.json` |
| Bank import — unmatched withdrawal | `bank-import-expense.json` |

## Template Structure

Each template contains:

```json
{
  "_meta": {
    "name": "Template name",
    "description": "When to use this template",
    "scenario": "Specific use case"
  },
  "_variables": {
    "variable_name": "description and type"
  },
  "_sequence": [
    "Ordered steps to execute"
  ],
  "records": {
    "record_name": {
      "_doc": "Step documentation",
      "_table": "Target table",
      "_operation": "add_records or update_records",
      "_requires": ["dependent variables"],
      "payload": { ... }
    }
  },
  "journal_entries": {
    "Summary of accounting entries"
  }
}
```

## How to Use Templates

### 1. Select the Appropriate Template

Read the `_meta.scenario` to confirm you have the right template.

### 2. Gather Required Variables

Check `_variables` section for all required data:

```json
"_variables": {
  "vendor_id": "integer - Vendor record ID",
  "bill_number": "string - Invoice/bill number from vendor",
  "date_timestamp": "integer - Unix timestamp",
  "amount": "number - Total amount including tax"
}
```

### 3. Follow the Sequence

Execute steps in order from `_sequence`. Each step corresponds to a record in `records`:

```
1. Create Bill record → get bill_id
2. Create BillLine → links to bill_id
3. Create Transaction → get entry_txn_id
...
```

### 4. Substitute Variables

Replace `{{variable}}` placeholders with actual values:

**Template:**
```json
{
  "Vendor": "{{vendor_id}}",
  "BillNumber": "{{bill_number}}",
  "Amount": "{{amount}}"
}
```

**Substituted:**
```json
{
  "Vendor": 1,
  "BillNumber": "INV-001",
  "Amount": 45.47
}
```

### 5. Track Generated IDs

Some steps require IDs from previous steps (noted in `_requires`):

- `bill_id` → returned from Bill creation
- `entry_txn_id` → returned from entry Transaction creation
- `payment_txn_id` → returned from payment Transaction creation

### 6. Run Audit

Always verify with audit queries after completing all steps.

## Key Account IDs

Quick reference for account substitution:

| Account | ID | Code | Use For |
|---------|-----|------|---------|
| Accounts Payable | 4 | 2000 | All bill entries |
| Checking Account | 14 | 1001 | Checking payments |
| Business Credit Card | 19 | 2101 | Credit card payments |
| Due to Owner | 22 | 2203 | Owner paid personally |
| Software & Subscriptions | 36 | 5080 | SaaS, API costs |
| Bank & Merchant Fees | 30 | 5020 | Bank fees |

## Formula Fields (Read-Only)

**Never include these fields in `add_records` payloads:**

| Table | Formula Fields |
|-------|----------------|
| Bills | Amount, AmountPaid, AmountDue |
| Transactions | Total, IsBalanced, Transaction_ID, Fiscal_Year |

These are calculated automatically by Grist.

## Example: Using bill-paid-credit-card.json

**Scenario:** Anthropic invoice #43I1T40F-0018 for $45.47 paid by credit card.

**Variables:**
```
vendor_id = 1 (Anthropic)
bill_number = "43I1T40F-0018"
date_timestamp = 1768435200 (Jan 14, 2026)
due_date_timestamp = 1768435200
amount = 45.47
expense_account_id = 36 (Software & Subscriptions)
line_description = "API auto-recharge credits"
vendor_name = "Anthropic"
receipt_number = "2687-3787-3014"
```

**Execution:**
1. `add_records("Bills", [payload])` → bill_id = 26
2. `add_records("BillLines", [payload])` → uses bill_id
3. `add_records("Transactions", [payload])` → entry_txn_id = 52
4. `add_records("TransactionLines", [payload])` → uses entry_txn_id
5. `update_records("Bills", [link payload])` → link Bill to Transaction
6. `add_records("Transactions", [payload])` → payment_txn_id = 53
7. `add_records("TransactionLines", [payload])` → uses payment_txn_id
8. `add_records("BillPayments", [payload])` → links bill to payment
9. `update_records("Bills", [{id: 26, fields: {Status: "Paid"}}])`
10. Upload attachments
11. Run audit

## SQL Reserved Words

When querying `TransactionLines`, the column `Transaction` is a SQL reserved word. Use `get_records` with filter instead of `sql_query`:

```python
# Instead of (fails):
sql_query("SELECT * FROM TransactionLines WHERE Transaction = 52")

# Use:
get_records("TransactionLines", filter={"Transaction": [52]})
```

## Available Templates

| File | Purpose |
|------|---------|
| [bill-paid-credit-card.json](../templates/bill-paid-credit-card.json) | Invoice paid by business credit card |
| [bill-paid-owner.json](../templates/bill-paid-owner.json) | Invoice paid by owner (reimbursement) |
| [bill-paid-checking.json](../templates/bill-paid-checking.json) | Invoice paid from checking account |
| [bill-unpaid.json](../templates/bill-unpaid.json) | Invoice recorded but not yet paid |
| [pay-existing-bill.json](../templates/pay-existing-bill.json) | Payment for previously entered bill |
| [direct-expense.json](../templates/direct-expense.json) | Direct expense without vendor bill |
| [bank-import-deposit.json](../templates/bank-import-deposit.json) | Unmatched bank deposit (interest, transfer in) |
| [bank-import-expense.json](../templates/bank-import-expense.json) | Unmatched bank withdrawal (ATM, check, ACH) |
