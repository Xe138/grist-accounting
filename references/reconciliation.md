# Bank Reconciliation

Import bank transactions, match against ledger entries, create missing transactions, and reconcile balances.

## Contents
- [Bank File Parsing](#bank-file-parsing)
- [Transaction Matching](#transaction-matching)
- [Creating Missing Transactions](#creating-missing-transactions)
- [Balance Reconciliation](#balance-reconciliation)
- [Queries](#queries)
- [Edge Cases](#edge-cases)

## Bank File Parsing

### Schwab JSON Format

Schwab exports a JSON file with this structure:

```json
{
  "FromDate": "MM/DD/YYYY",
  "ToDate": "MM/DD/YYYY",
  "PendingTransactions": [],
  "PostedTransactions": [
    {
      "CheckNumber": null,
      "Description": "Interest Paid",
      "Date": "MM/DD/YYYY",
      "RunningBalance": "$1,500.01",
      "Withdrawal": "",
      "Deposit": "$0.01",
      "Type": "INTADJUST"
    }
  ]
}
```

### Parsing Rules

1. **Date**: Convert `MM/DD/YYYY` → Unix timestamp. Example: `01/14/2026` → `1736812800`
2. **Amount**: Parse `$` strings, remove commas. `Deposit` = positive, `Withdrawal` = negative. Empty string = no amount.
3. **Sort**: By date ascending after parsing
4. **Zero-amount entries**: Flag for user review (e.g., `INTADJUST` with no Deposit/Withdrawal)
5. **Statement ending balance**: Extract from last entry's `RunningBalance` (chronologically latest)

### Date Conversion Reference

Use Jan 1, 2026 = 1767312000 as base, add `days * 86400`.

| Date String | Unix Timestamp | Calculation |
|-------------|---------------|-------------|
| 12/31/2025 | 1767225600 | Jan 1 - 1 day |
| 01/14/2026 | 1768435200 | Jan 1 + 13 days |
| 01/30/2026 | 1769817600 | Jan 1 + 29 days |
| 02/17/2026 | 1771372800 | Jan 1 + 47 days |

### Type Field Mapping

| Bank Type | Suggested Offset Account | Notes |
|-----------|-------------------------|-------|
| `INTADJUST` | Interest Income (4010, id=26) | Bank interest payments |
| `TRANSFER` | Owner's Investment (3001, id=23) | Incoming transfers — confirm with user |
| `ATM` | Owner's Draws (3002, id=24) | ATM withdrawals |
| `CHECK` | Prompt user | Check payments |
| `ACH` | Prompt user | ACH debits |
| `DEBIT` | Prompt user | Debit card transactions |

## Transaction Matching

### Algorithm

For each bank transaction, find a matching ledger entry:

1. Fetch all TransactionLines for the bank account using `get_records` (not `sql_query` — `Transaction` is a reserved word)
2. For each bank transaction with an amount:
   - Find ledger entries where: **exact amount match** AND **date within ±3 days** AND **not already matched**
   - Deposits match TransactionLines where `Debit > 0` (money into checking = debit to asset)
   - Withdrawals match TransactionLines where `Credit > 0` (money out of checking = credit to asset)
3. Mark each bank entry: **Matched**, **Unmatched**, or **Skipped** (no amount)
4. Mark each ledger entry: **Matched** or **Outstanding**

### Matching with get_records

```python
# Fetch all TransactionLines for Checking Account (id=14)
get_records("TransactionLines", filter={"Account": [14]})

# Then fetch transaction details for date comparison
# Get unique transaction IDs from the lines, then:
sql_query("SELECT id, Date, Description, Status FROM Transactions WHERE id IN (id1, id2, ...)")
```

### Match Classification

| Bank Entry | Ledger Entry | Classification |
|------------|-------------|----------------|
| Has match | Has match | **Matched** — both confirmed |
| No match | — | **Unmatched (bank only)** — needs new ledger entry |
| No amount | — | **Skipped** — review manually |
| — | No match | **Outstanding** — in ledger but not cleared by bank |

## Creating Missing Transactions

For each unmatched bank transaction:

### 1. Check BankRules

```python
get_records("BankRules", filter={"Account": [14], "IsActive": [true]})
```

For each rule, check if the bank description matches the pattern:
- **Contains**: pattern is a substring of bank description
- **Starts With**: bank description starts with pattern
- **Exact**: bank description equals pattern

If a rule matches, auto-fill the offset account and description.

### 2. Determine Offset Account

Use the Type field mapping above as a suggestion. Always confirm with user for ambiguous types.

### 3. Create Transaction

Use the bank-import templates:
- **Deposits** → `bank-import-deposit.json` (Dr Checking, Cr Offset)
- **Withdrawals** → `bank-import-expense.json` (Dr Offset, Cr Checking)

All imported transactions use `Status = "Cleared"` since the bank confirms them.

### 4. Optionally Save BankRule

If user agrees, create a BankRule for future auto-categorization:

```python
add_records("BankRules", [{
    "Account": 14,
    "Pattern": "Interest Paid",
    "MatchType": "Contains",
    "OffsetAccount": 26,
    "TransactionDescription": "Bank interest income",
    "IsActive": true
}])
```

## Balance Reconciliation

### Calculate Cleared Balance

After matching and creating missing transactions:

```python
# Get all TransactionLines for Checking Account
lines = get_records("TransactionLines", filter={"Account": [14]})

# Get transaction IDs and filter for Cleared status
txn_ids = [unique transaction IDs from lines]
cleared_txns = sql_query("SELECT id FROM Transactions WHERE Status = 'Cleared' AND id IN (...)")

# Sum: Debit - Credit for cleared lines only
cleared_balance = sum(line.Debit - line.Credit for line in lines if line.Transaction in cleared_txn_ids)
```

### Reconciliation Record

```python
# Create reconciliation record
add_records("Reconciliations", [{
    "Account": 14,
    "StatementDate": statement_date_timestamp,
    "StatementBalance": statement_balance,
    "ClearedBalance": cleared_balance,
    "Difference": statement_balance - cleared_balance,
    "Status": "In Progress",
    "StartedAt": today_timestamp,
    "Notes": "Reconciling against Schwab export"
}])
```

### Finalization

- **Difference = $0**: Update Status to "Completed", set CompletedAt
- **Difference ≠ $0**: Report discrepancy, list outstanding items, offer options:
  1. Review unmatched items
  2. Create adjusting entry
  3. Save progress and return later

## Queries

### Cleared Balance for Account

```python
# Use get_records to avoid Transaction reserved word issue
lines = get_records("TransactionLines", filter={"Account": [14]})
# Then filter by cleared transactions and sum Debit - Credit
```

### Outstanding Items (in ledger, not cleared)

```sql
SELECT t.id, t.Date, t.Description, t.Status,
       tl.Debit, tl.Credit
FROM TransactionLines tl
JOIN Transactions t ON tl.Transaction = t.id
WHERE tl.Account = 14
  AND t.Status != 'Cleared'
ORDER BY t.Date
```

### Reconciliation History

```sql
SELECT r.id, r.StatementDate, r.StatementBalance,
       r.ClearedBalance, r.Difference, r.Status
FROM Reconciliations r
WHERE r.Account = 14
ORDER BY r.StatementDate DESC
```

### Unmatched Bank Rules

```python
get_records("BankRules", filter={"Account": [14], "IsActive": [true]})
```

## Edge Cases

### Zero-Amount Entries

Some bank entries (e.g., `INTADJUST` with empty Deposit and Withdrawal) have no monetary value. Skip these during matching and creation but report them to the user.

### Duplicate Amounts

When multiple bank transactions have the same amount, use date proximity as the tiebreaker. If still ambiguous, present options to the user.

### Re-imports

If the same bank file is imported again, the matching phase will find existing ledger entries for previously imported transactions. Only truly new entries will be unmatched.

### Partial Reconciliation

If the user can't resolve all differences in one session, save the Reconciliation with Status="In Progress". Resume later by loading the record and continuing from Phase 2.
