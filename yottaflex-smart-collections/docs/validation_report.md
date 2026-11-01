# Validation report

## Environment checks recorded
- PostgreSQL 16 health check accepted connections.
- `GET /health` returned status `ok`.
- A local dashboard snapshot returned customers 10,004; accounts 10,002; loans 10,002; installments 30,002; open cases 7,104; on-hold 0; open exceptions 1; payments 14,134.
- Earlier local pytest run: 2 passed, 1 deprecation warning. Re-run after packaging.

## Scenarios
| Scenario | Observed evidence | Status |
|---|---|---|
| Paid-off loan remains in collections | Loan `LOAN-2026-008027` updated to PAID_OFF; case `CASE-SYN-005698` remained OPEN, HIGH, score 92 | Anomaly confirmed |
| Contact outside permitted window | `CONTACT-ANOMALY-002`, case `CASE-SYN-000024`; HTTP 201, permitted=false, outcome=RESTRICTED; checks: weekday not permitted and outside window | Policy enforcement confirmed |
| Payment allocated to wrong loan's installment | Payment `PAY-ANOMALY-003` on `ACC-2026-000030` attempted against `INS-LOAN-2026-000031-001`; HTTP 422: Payment account does not match installment loan account | Negative test passed; bad allocation not persisted |
| Promise greater than arrears | Not tested | Outstanding |
| Disputed debt treated as confirmed | Not tested; dispute lifecycle flag needs verification | Outstanding |

201 on restricted contact means record created, not contact permitted. 422 on cross-account allocation means the guard blocked the invalid allocation.
