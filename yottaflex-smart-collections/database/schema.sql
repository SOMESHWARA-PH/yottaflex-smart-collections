-- YottaFlex Smart Collections: initial relational schema.
-- Amounts use NUMERIC. Timestamps use TIMESTAMPTZ.
-- Do not put ground-truth labels in these operational tables.

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(40) PRIMARY KEY,
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(254),
    phone VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id VARCHAR(40) PRIMARY KEY,
    customer_id VARCHAR(40) NOT NULL REFERENCES customers(customer_id),
    account_status VARCHAR(20) NOT NULL CHECK (account_status IN ('ACTIVE','CLOSED','FROZEN')),
    opened_at DATE NOT NULL,
    closed_at DATE,
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE IF NOT EXISTS loans (
    loan_id VARCHAR(40) PRIMARY KEY,
    account_id VARCHAR(40) NOT NULL REFERENCES accounts(account_id),
    principal_amount NUMERIC(14,2) NOT NULL CHECK (principal_amount > 0),
    annual_interest_rate NUMERIC(7,4) NOT NULL CHECK (annual_interest_rate >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    start_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    loan_status VARCHAR(20) NOT NULL CHECK (loan_status IN ('ACTIVE','PAID_OFF','CLOSED','DEFAULTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (maturity_date > start_date)
);

CREATE TABLE IF NOT EXISTS installments (
    installment_id VARCHAR(80) PRIMARY KEY,
    loan_id VARCHAR(40) NOT NULL REFERENCES loans(loan_id),
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    due_date DATE NOT NULL,
    principal_due NUMERIC(14,2) NOT NULL CHECK (principal_due >= 0),
    interest_due NUMERIC(14,2) NOT NULL CHECK (interest_due >= 0),
    fees_due NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (fees_due >= 0),
    installment_status VARCHAR(20) NOT NULL CHECK (installment_status IN ('SCHEDULED','PARTIALLY_PAID','PAID','OVERDUE','CANCELLED')),
    UNIQUE (loan_id, installment_number)
);

CREATE TABLE IF NOT EXISTS delinquency_snapshots (
    snapshot_id VARCHAR(40) PRIMARY KEY,
    loan_id VARCHAR(40) NOT NULL REFERENCES loans(loan_id),
    as_of_date DATE NOT NULL,
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    arrears_amount NUMERIC(14,2) NOT NULL CHECK (arrears_amount >= 0),
    outstanding_balance NUMERIC(14,2) NOT NULL CHECK (outstanding_balance >= 0),
    overdue_installment_count INTEGER NOT NULL CHECK (overdue_installment_count >= 0),
    calculation_version VARCHAR(30) NOT NULL,
    UNIQUE (loan_id, as_of_date, calculation_version)
);

CREATE TABLE IF NOT EXISTS contact_preferences (
    preference_id VARCHAR(40) PRIMARY KEY,
    customer_id VARCHAR(40) NOT NULL REFERENCES customers(customer_id),
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('PHONE','SMS','EMAIL','POST')),
    allowed_weekdays SMALLINT[] NOT NULL,
    window_start TIME NOT NULL,
    window_end TIME NOT NULL,
    timezone VARCHAR(64) NOT NULL,
    opted_out BOOLEAN NOT NULL DEFAULT FALSE,
    effective_from DATE NOT NULL,
    effective_to DATE,
    CHECK (window_end > window_start),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (0 <= ALL(allowed_weekdays) AND 6 >= ALL(allowed_weekdays))
);

CREATE TABLE IF NOT EXISTS collection_cases (
    case_id VARCHAR(40) PRIMARY KEY,
    loan_id VARCHAR(40) NOT NULL REFERENCES loans(loan_id),
    opened_at TIMESTAMPTZ NOT NULL,
    case_status VARCHAR(20) NOT NULL CHECK (case_status IN ('OPEN','ON_HOLD','RESOLVED','CLOSED')),
    priority_score NUMERIC(6,2) NOT NULL CHECK (priority_score BETWEEN 0 AND 100),
    priority_band VARCHAR(10) NOT NULL CHECK (priority_band IN ('LOW','MEDIUM','HIGH')),
    score_explanation JSONB NOT NULL,
    hold_reason VARCHAR(40),
    resolved_at TIMESTAMPTZ,
    CHECK (resolved_at IS NULL OR resolved_at >= opened_at)
);

CREATE TABLE IF NOT EXISTS contact_attempts (
    contact_attempt_id VARCHAR(60) PRIMARY KEY,
    case_id VARCHAR(40) NOT NULL REFERENCES collection_cases(case_id),
    customer_id VARCHAR(40) NOT NULL REFERENCES customers(customer_id),
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('PHONE','SMS','EMAIL','POST')),
    scheduled_at TIMESTAMPTZ NOT NULL,
    attempted_at TIMESTAMPTZ,
    outcome VARCHAR(30) CHECK (outcome IN ('REACHED','NO_ANSWER','MESSAGE_SENT','CUSTOMER_REQUESTED_CALLBACK','RESTRICTED','FAILED')),
    restriction_check_passed BOOLEAN NOT NULL DEFAULT FALSE,
    restriction_check_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS promises_to_pay (
    promise_id VARCHAR(60) PRIMARY KEY,
    case_id VARCHAR(40) NOT NULL REFERENCES collection_cases(case_id),
    promised_amount NUMERIC(14,2) NOT NULL CHECK (promised_amount > 0),
    promised_date DATE NOT NULL,
    promise_status VARCHAR(20) NOT NULL CHECK (promise_status IN ('PENDING','FULFILLED','PARTIALLY_FULFILLED','MISSED','CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(40) PRIMARY KEY,
    account_id VARCHAR(40) NOT NULL REFERENCES accounts(account_id),
    received_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('BANK_TRANSFER','UPI','CARD','CASH','OTHER')),
    external_reference VARCHAR(100) UNIQUE
);

-- Bridge table: a payment may settle multiple installments and an installment
-- may be settled by multiple payments.
CREATE TABLE IF NOT EXISTS payment_allocations (
    allocation_id BIGSERIAL PRIMARY KEY,
    payment_id VARCHAR(40) NOT NULL REFERENCES payments(payment_id),
    installment_id VARCHAR(80) NOT NULL REFERENCES installments(installment_id),
    allocated_amount NUMERIC(14,2) NOT NULL CHECK (allocated_amount > 0),
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    allocation_status VARCHAR(20) NOT NULL CHECK (allocation_status IN ('PROPOSED','CONFIRMED','REVERSED')),
    UNIQUE (payment_id, installment_id, allocation_status)
);

CREATE TABLE IF NOT EXISTS promise_payment_allocations (
    promise_allocation_id VARCHAR(60) PRIMARY KEY,
    promise_id VARCHAR(60) NOT NULL REFERENCES promises_to_pay(promise_id),
    payment_id VARCHAR(40) NOT NULL REFERENCES payments(payment_id),
    allocated_amount NUMERIC(14,2) NOT NULL CHECK (allocated_amount > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (promise_id, payment_id)
);

CREATE TABLE IF NOT EXISTS collection_case_events (
    event_id BIGSERIAL PRIMARY KEY,
    case_id VARCHAR(40) NOT NULL REFERENCES collection_cases(case_id),
    previous_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    actor_type VARCHAR(20) NOT NULL CHECK (actor_type IN ('SYSTEM','ANALYST','REVIEWER','ADMIN')),
    actor_id VARCHAR(60),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS exception_records (
    exception_id VARCHAR(50) PRIMARY KEY,
    case_id VARCHAR(40) REFERENCES collection_cases(case_id),
    loan_id VARCHAR(40) REFERENCES loans(loan_id),
    issue_type VARCHAR(50) NOT NULL,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exception_status VARCHAR(20) NOT NULL CHECK (exception_status IN ('OPEN','UNDER_REVIEW','RESOLVED','FALSE_POSITIVE')),
    details JSONB NOT NULL,
    resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_installments_loan_due ON installments(loan_id, due_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_asof_dpd ON delinquency_snapshots(as_of_date, days_past_due);
CREATE INDEX IF NOT EXISTS idx_cases_status_priority ON collection_cases(case_status, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_case_schedule ON contact_attempts(case_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_promises_status_date ON promises_to_pay(promise_status, promised_date);
CREATE INDEX IF NOT EXISTS idx_exceptions_status_severity ON exception_records(exception_status, severity);
