from sqlalchemy import (
    Column, String, DateTime, Date, ForeignKey, Numeric, Integer, Boolean,
    Time, Text, SmallInteger, BigInteger, UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.db import Base


class Customer(Base):
    __tablename__ = "customers"
    customer_id = Column(String(40), primary_key=True)
    full_name = Column(String(160), nullable=False)
    email = Column(String(254))
    phone = Column(String(30))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"
    account_id = Column(String(40), primary_key=True)
    customer_id = Column(String(40), ForeignKey("customers.customer_id"), nullable=False)
    account_status = Column(String(20), nullable=False)
    opened_at = Column(Date, nullable=False)
    closed_at = Column(Date)


class Loan(Base):
    __tablename__ = "loans"
    loan_id = Column(String(40), primary_key=True)
    account_id = Column(String(40), ForeignKey("accounts.account_id"), nullable=False)
    principal_amount = Column(Numeric(14, 2), nullable=False)
    annual_interest_rate = Column(Numeric(7, 4), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    start_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    loan_status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Installment(Base):
    __tablename__ = "installments"
    __table_args__ = (UniqueConstraint("loan_id", "installment_number", name="uq_installment_loan_number"),)
    installment_id = Column(String(80), primary_key=True)
    loan_id = Column(String(40), ForeignKey("loans.loan_id"), nullable=False)
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    principal_due = Column(Numeric(14, 2), nullable=False)
    interest_due = Column(Numeric(14, 2), nullable=False)
    fees_due = Column(Numeric(14, 2), nullable=False, default=0)
    installment_status = Column(String(20), nullable=False)


class DelinquencySnapshot(Base):
    __tablename__ = "delinquency_snapshots"
    __table_args__ = (UniqueConstraint("loan_id", "as_of_date", "calculation_version", name="uq_snapshot_loan_date_version"),)
    snapshot_id = Column(String(40), primary_key=True)
    loan_id = Column(String(40), ForeignKey("loans.loan_id"), nullable=False)
    as_of_date = Column(Date, nullable=False)
    days_past_due = Column(Integer, nullable=False)
    arrears_amount = Column(Numeric(14, 2), nullable=False)
    outstanding_balance = Column(Numeric(14, 2), nullable=False)
    overdue_installment_count = Column(Integer, nullable=False)
    calculation_version = Column(String(30), nullable=False)


class ContactPreference(Base):
    __tablename__ = "contact_preferences"
    preference_id = Column(String(40), primary_key=True)
    customer_id = Column(String(40), ForeignKey("customers.customer_id"), nullable=False)
    channel = Column(String(20), nullable=False)
    allowed_weekdays = Column(ARRAY(SmallInteger), nullable=False)
    window_start = Column(Time, nullable=False)
    window_end = Column(Time, nullable=False)
    timezone = Column(String(64), nullable=False)
    opted_out = Column(Boolean, nullable=False, default=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)


class CollectionCase(Base):
    __tablename__ = "collection_cases"
    case_id = Column(String(40), primary_key=True)
    loan_id = Column(String(40), ForeignKey("loans.loan_id"), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    case_status = Column(String(20), nullable=False)
    priority_score = Column(Numeric(6, 2), nullable=False)
    priority_band = Column(String(10), nullable=False)
    score_explanation = Column(JSONB, nullable=False)
    hold_reason = Column(String(40))
    resolved_at = Column(DateTime(timezone=True))


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"
    contact_attempt_id = Column(String(60), primary_key=True)
    case_id = Column(String(40), ForeignKey("collection_cases.case_id"), nullable=False)
    customer_id = Column(String(40), ForeignKey("customers.customer_id"), nullable=False)
    channel = Column(String(20), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    attempted_at = Column(DateTime(timezone=True))
    outcome = Column(String(30))
    restriction_check_passed = Column(Boolean, nullable=False, default=False)
    restriction_check_details = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PromiseToPay(Base):
    __tablename__ = "promises_to_pay"
    promise_id = Column(String(60), primary_key=True)
    case_id = Column(String(40), ForeignKey("collection_cases.case_id"), nullable=False)
    promised_amount = Column(Numeric(14, 2), nullable=False)
    promised_date = Column(Date, nullable=False)
    promise_status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"
    payment_id = Column(String(40), primary_key=True)
    account_id = Column(String(40), ForeignKey("accounts.account_id"), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    payment_method = Column(String(20), nullable=False)
    external_reference = Column(String(100), unique=True)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (UniqueConstraint("payment_id", "installment_id", "allocation_status", name="uq_payment_installment_status"),)
    allocation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    payment_id = Column(String(40), ForeignKey("payments.payment_id"), nullable=False)
    installment_id = Column(String(80), ForeignKey("installments.installment_id"), nullable=False)
    allocated_amount = Column(Numeric(14, 2), nullable=False)
    allocated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    allocation_status = Column(String(20), nullable=False)


class CollectionCaseEvent(Base):
    __tablename__ = "collection_case_events"
    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    case_id = Column(String(40), ForeignKey("collection_cases.case_id"), nullable=False)
    previous_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    event_type = Column(String(40), nullable=False)
    actor_type = Column(String(20), nullable=False)
    actor_id = Column(String(60))
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reason = Column(Text, nullable=False)
    event_metadata = Column("metadata", JSONB, nullable=False, default=dict)


class ExceptionRecord(Base):
    __tablename__ = "exception_records"
    exception_id = Column(String(50), primary_key=True)
    case_id = Column(String(40), ForeignKey("collection_cases.case_id"))
    loan_id = Column(String(40), ForeignKey("loans.loan_id"))
    issue_type = Column(String(50), nullable=False)
    severity = Column(String(10), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    exception_status = Column(String(20), nullable=False)
    details = Column(JSONB, nullable=False)
    resolution_note = Column(Text)


class PromisePaymentAllocation(Base):
    __tablename__ = "promise_payment_allocations"
    promise_allocation_id = Column(String(60), primary_key=True)
    promise_id = Column(String(60), ForeignKey("promises_to_pay.promise_id"), nullable=False)
    payment_id = Column(String(40), ForeignKey("payments.payment_id"), nullable=False)
    allocated_amount = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("promise_id", "payment_id", name="uq_promise_payment"),)
