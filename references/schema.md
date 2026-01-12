# Database Schema

Complete table schemas for the Grist accounting system.

## Accounts
| Column | Type | Notes |
|--------|------|-------|
| Code | Text | Account number (e.g., "5080") |
| Name | Text | Account name |
| Type | Choice | "Asset", "Liability", "Equity", "Income", "Expense" |
| Parent | Ref:Accounts | Parent account for hierarchy (0 = top-level) |
| Description | Text | |
| IsActive | Bool | |
| Balance | Formula | Calculated from transactions |

## Vendors
| Column | Type | Notes |
|--------|------|-------|
| Name | Text | Vendor name |
| DefaultExpenseAccount | Ref:Accounts | Auto-fills on bill lines |
| PaymentTerms | Choice | "Due on Receipt", "Net 15", "Net 30" |
| Notes | Text | |
| IsActive | Bool | |
| Balance | Formula | Sum of unpaid bills |

## Items
| Column | Type | Notes |
|--------|------|-------|
| Name | Text | Item name (e.g., "Software Subscription") |
| DefaultAccount | Ref:Accounts | Expense account for this item |
| DefaultDescription | Text | Auto-fills on bill lines |
| IsActive | Bool | |

## Bills
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

## BillLines
| Column | Type | Notes |
|--------|------|-------|
| Bill | Ref:Bills | Required |
| Item | Ref:Items | Optional - auto-fills Account/Description |
| Account | Ref:Accounts | Expense account |
| Description | Text | |
| Amount | Numeric | Line item amount |

## Transactions
| Column | Type | Notes |
|--------|------|-------|
| Date | Date | Unix timestamp |
| Description | Text | Transaction description |
| Reference | Text | Check number, invoice reference, etc. |
| Status | Choice | "Draft", "Posted", "Cleared" |
| Memo | Text | |
| Total | Formula | Sum of debits |
| IsBalanced | Formula | True if debits = credits |

## TransactionLines
| Column | Type | Notes |
|--------|------|-------|
| Transaction | Ref:Transactions | Required |
| Account | Ref:Accounts | Required |
| Debit | Numeric | Debit amount (or 0) |
| Credit | Numeric | Credit amount (or 0) |
| Memo | Text | |

## BillPayments
| Column | Type | Notes |
|--------|------|-------|
| Bill | Ref:Bills | Required |
| Transaction | Ref:Transactions | Payment journal entry |
| Amount | Numeric | Payment amount |
| PaymentDate | Date | Unix timestamp |

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
