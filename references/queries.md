# SQL Queries and Reports

Common queries and financial report templates.

## Contents
- [Common Queries](#common-queries)
- [Financial Reports](#financial-reports)
  - [Balance Sheet](#balance-sheet)
  - [Income Statement](#income-statement)
  - [Trial Balance](#trial-balance)
  - [AP Aging](#accounts-payable-aging)

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
WHERE tl.Account = {account_id}
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
