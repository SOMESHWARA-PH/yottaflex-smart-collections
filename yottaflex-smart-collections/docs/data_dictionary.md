# Data dictionary

| Entity | Key | Main fields and validation |
|---|---|---|
| Customer | customer_id | full_name required; email/phone optional; synthetic only |
| Account | account_id | customer FK; ACTIVE/CLOSED/FROZEN; opened/closed dates |
| Loan | loan_id | account FK; principal >0; rate >=0; currency; ACTIVE/PAID_OFF/CLOSED/DEFAULTED |
| Installment | installment_id | loan FK; unique loan+number; principal/interest/fees >=0; due date/status |
| DelinquencySnapshot | snapshot_id | loan FK; as-of date; DPD, arrears, outstanding, overdue count, calculation version |
| ContactPreference | preference_id | customer FK; channel; weekdays 0=Mon..6=Sun; local time window; IANA timezone; opt-out; effective dates |
| CollectionCase | case_id | loan FK; status; score 0..100; priority band; JSON explanation; hold/resolution |
| ContactAttempt | contact_attempt_id | case/customer FK; channel; schedule/attempt timestamps; outcome; restriction details |
| PromiseToPay | promise_id | case FK; positive amount; due date; PENDING/FULFILLED/PARTIALLY_FULFILLED/MISSED/CANCELLED |
| Payment | payment_id | account FK; received time; positive amount; currency/method; unique external ref |
| PaymentAllocation | allocation_id | payment/installment FKs; positive amount; PROPOSED/CONFIRMED/REVERSED |
| PromisePaymentAllocation | promise_allocation_id | promise/payment FKs; positive amount; unique promise/payment pair |
| CollectionCaseEvent | event_id | case FK; previous/new status; actor, time, reason, metadata |
| ExceptionRecord | exception_id | optional case/loan FK; issue, severity, status, JSON details |

Synthetic development assumptions: fixed seed 20261022; 10,000 base customers/accounts/loans; 30,000 installments; 10,000 preferences and snapshots. Contact preference test population used PHONE, weekdays sampled Monday–Saturday, 09:00–11:00 starts, 17:00–19:00 ends, Asia/Kolkata, and 8.15% opt-out. These are synthetic scenario assumptions, not population statistics. DPD, arrears, balances, score and band should be derived from source transactions and stored with as-of/calculation version.
