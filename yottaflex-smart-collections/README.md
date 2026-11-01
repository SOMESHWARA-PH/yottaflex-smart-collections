# YottaFlex Smart Collections Management & Delinquency Prioritization

Synthetic-data-driven prototype for overdue-loan prioritization, compliant contact scheduling, payment allocation, promise-to-pay monitoring and exception review.

## Stack
FastAPI + SQLAlchemy + Pydantic, PostgreSQL 16, React 18 + Vite.

## Run locally (Windows PowerShell)
1. Install Python 3.11+, Node.js 20+, Docker Desktop.
2. Copy `.env.example` to `.env` (never commit `.env`).
3. From root: `docker compose up -d db`
4. Apply schema: `Get-Content .\database\schema.sql | docker exec -i yottaflex-postgres psql -U collections_user -d collections_db`
5. Backend: `cd backend`; `python -m venv .venv`; `.venv\Scripts\Activate.ps1`; `pip install -r requirements.txt`; `python -m uvicorn app.main:app --reload --port 8000`.
6. Frontend: `cd frontend`; `npm install`; `npm run dev`. Open `http://localhost:5173`; API docs at `http://127.0.0.1:8000/docs`.

Linux/macOS activation: `source .venv/bin/activate`; schema import: `docker compose exec -T db psql -U collections_user -d collections_db < database/schema.sql`.

## API highlights
`GET /health`; `GET /api/v1/dashboard/summary`; customer/account/loan/installment/snapshot create/list/get endpoints; loan status update; contact preference and contact attempt; payment and payment allocation; case create/list/status update; promises and promise-payment allocations; promise reconciliation; exception create/list.

## Business rules
- Amounts use NUMERIC, timestamps are timezone-aware.
- Case priority score is bounded 0–100 and includes a JSON explanation.
- Contact attempts check active preference, opt-out, allowed weekday, local-time window and rolling frequency. Restricted attempts are stored as RESTRICTED with check details; HTTP 201 means recorded, not permitted.
- Payment allocation verifies that payment account matches the account owning the installment loan.
- Promise payment linking checks account ownership, confirmed installment allocation and amount caps.
- Case status changes create an audit event. Ground truth is external and not an operational model input.

## Evidence and status
The development database was previously checked locally: 10,004 customers, 10,002 accounts, 10,002 loans, 30,002 installments, 7,104 open cases and 14,134 payments. These are historical local DB counts, not generated automatically by this repository. `docs/validation_report.md` records verified scenarios. Two anomalies are evidence-backed; a third test verifies the API rejects a cross-account allocation. Remaining anomaly scenarios are explicitly marked outstanding.

Packaged test suite: 4 passed using a SQLite URL for the health route and Pydantic validation tests; this is not a PostgreSQL integration test. Re-run `cd backend; python -m pytest tests -v` in the configured development environment. Run `python scripts/validate_ground_truth.py` from the repository root.

## Reproducibility / limitations
The local development database used seed `20261022`; a complete deterministic master-data generator and database export are not included in this package. Export only reviewed synthetic data if needed: `docker exec yottaflex-postgres pg_dump -U collections_user -d collections_db --no-owner --no-acl > data/generated/yottaflex_synthetic.sql`. Review the export before committing. Authentication, role-based authorization, migrations, full integration tests, pagination and full deterministic rebuild are future work.

## AI disclosure
See `docs/AI_USAGE.md`. AI assistance was used for implementation guidance, debugging, test design and documentation. Candidate must personally understand and validate the code.
