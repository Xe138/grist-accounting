---
name: grist-accounting
description: Use when working with the Grist double-entry accounting system - recording transactions, entering bills, tracking vendors, querying account balances, or generating financial reports
---

# Grist Double-Entry Accounting System

## Overview

A complete double-entry accounting system for sole proprietorship service businesses. Every transaction creates balanced journal entries (debits = credits). Account balances roll up through parent-child hierarchy.

## Schema Quick Reference

| Table | Purpose | Key Fields |
|-------|---------|------------|
| Accounts | Chart of accounts | Code, Name, Type, Parent, Balance |
| Transactions | Journal entry headers | Date, Description, Reference, Status |
| TransactionLines | Debits and credits | Transaction, Account, Debit, Credit |
| Vendors | People you pay | Name, PaymentTerms, Balance |
| Items | Common purchases | Name, DefaultAccount |
| Bills | AP invoices | Vendor, BillDate, DueDate, Status, Amount, AmountDue |
| BillLines | Bill line items | Bill, Item, Account, Amount |
| BillPayments | Payment tracking | Bill, Transaction, Amount |
| ReportingPeriods | Date ranges | Name, StartDate, EndDate, IsClosed |

## Account Types

| Type | Normal Balance | Examples |
|------|----------------|----------|
| Asset | Debit | Cash, AR, Prepaid |
| Liability | Credit | AP, Credit Cards, Due to Owner |
| Equity | Credit | Owner's Investment, Draws, Retained Earnings |
| Income | Credit | Service Revenue, Interest Income |
| Expense | Debit | Rent, Utilities, Office Supplies |

## Common Workflows

### Record a Simple Expense

```python
# Pay $50 for office supplies from checking
transaction = add_records("Transactions", [{
    "Date": "2026-01-03",
    "Description": "Office supplies",
    "Status": "Cleared"
}])

add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": office_supplies_id, "Debit": 50},
    {"Transaction": txn_id, "Account": checking_id, "Credit": 50}
])
```

### Enter a Bill (Accounts Payable)

1. Create Bill record with Vendor, BillDate, DueDate
2. Add BillLines with Item/Account and Amount
3. Create Transaction: Debit expense accounts, Credit AP
4. Link Bill.EntryTransaction to the transaction

```python
# $150 electric bill from vendor
bill = add_records("Bills", [{
    "Vendor": vendor_id,
    "BillDate": "2026-01-03",
    "DueDate": "2026-02-02",
    "Status": "Open"
}])

add_records("BillLines", [{
    "Bill": bill_id,
    "Account": utilities_id,
    "Description": "January electric",
    "Amount": 150
}])

# Journal entry
txn = add_records("Transactions", [{
    "Date": "2026-01-03",
    "Description": "Electric Co - January"
}])

add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": utilities_id, "Debit": 150},
    {"Transaction": txn_id, "Account": ap_id, "Credit": 150}
])

# Link bill to transaction
update_records("Bills", [{"id": bill_id, "fields": {"EntryTransaction": txn_id}}])
```

### Pay a Bill

```python
# Pay $150 bill
txn = add_records("Transactions", [{
    "Date": "2026-01-15",
    "Description": "Payment - Electric Co",
    "Reference": "Check #1001"
}])

add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": ap_id, "Debit": 150},
    {"Transaction": txn_id, "Account": checking_id, "Credit": 150}
])

add_records("BillPayments", [{
    "Bill": bill_id,
    "Transaction": txn_id,
    "Amount": 150,
    "PaymentDate": "2026-01-15"
}])

# Bill.Status auto-updates based on AmountDue formula
```

### Owner Reimbursement

When owner pays business expense personally:
```python
# Debit expense, Credit "Due to Owner" (liability 2203)
add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": expense_id, "Debit": 50},
    {"Transaction": txn_id, "Account": due_to_owner_id, "Credit": 50}
])
```

When business reimburses owner:
```python
# Debit "Due to Owner", Credit Checking
add_records("TransactionLines", [
    {"Transaction": txn_id, "Account": due_to_owner_id, "Debit": 50},
    {"Transaction": txn_id, "Account": checking_id, "Credit": 50}
])
```

## Querying Data

### Get Account Balances

```python
# All accounts with balances
sql_query("SELECT Code, Name, Type, Balance FROM Accounts ORDER BY Code")

# Cash accounts only
sql_query("SELECT Name, Balance FROM Accounts WHERE Parent = 1")  # Parent 1 = Cash

# Total by account type
sql_query("SELECT Type, SUM(Balance) FROM Accounts WHERE Parent IS NULL GROUP BY Type")
```

### Get Unpaid Bills

```python
sql_query("""
    SELECT v.Name, b.BillNumber, b.DueDate, b.AmountDue
    FROM Bills b
    JOIN Vendors v ON b.Vendor = v.id
    WHERE b.Status IN ('Open', 'Partial')
    ORDER BY b.DueDate
""")
```

### Transaction History for Account

```python
sql_query("""
    SELECT t.Date, t.Description, tl.Debit, tl.Credit
    FROM TransactionLines tl
    JOIN Transactions t ON tl.Transaction = t.id
    WHERE tl.Account = ?
    ORDER BY t.Date DESC
""", account_id)
```

## Key Account Codes

| Code | Name | Use For |
|------|------|---------|
| 1001 | Checking Account | Primary bank account |
| 2000 | Accounts Payable | Bills owed to vendors |
| 2203 | Due to Owner | Owner reimbursements |
| 3002 | Owner's Draws | Money withdrawn by owner |
| 4001 | Service Revenue | Primary income |

## Validation Rules

1. **Transactions must balance**: `SUM(Debit) = SUM(Credit)`
2. **Each line has Debit OR Credit**, not both
3. **Bills need at least one BillLine**
4. **BillPayments cannot exceed AmountDue**

## Formula Columns (Auto-Calculated)

| Table.Column | Formula |
|--------------|---------|
| Accounts.Balance | OwnBalance + ChildrenBalance |
| Transactions.IsBalanced | Sum debits = Sum credits |
| Bills.Amount | Sum of BillLines.Amount |
| Bills.AmountDue | Amount - AmountPaid |
| Vendors.Balance | Sum of unpaid bills |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Transaction not balanced | Ensure debits = credits before saving |
| Wrong debit/credit direction | Assets/Expenses increase with debit; Liabilities/Equity/Income increase with credit |
| Posting to parent account | Post to leaf accounts (1001 Checking, not 1000 Cash) |
| Forgetting AP entry for bills | Bills need both the expense entry AND the AP credit |
