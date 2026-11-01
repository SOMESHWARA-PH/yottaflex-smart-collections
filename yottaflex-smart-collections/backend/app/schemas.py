from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=40)
    full_name: str = Field(min_length=1, max_length=160)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class CustomerResponse(ORMModel):
    customer_id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class AccountCreate(BaseModel):
    account_id: str
    customer_id: str
    account_status: Literal["ACTIVE", "CLOSED", "FROZEN"]
    opened_at: date
    closed_at: Optional[date] = None

class AccountResponse(ORMModel):
    account_id: str
    customer_id: str
    account_status: str
    opened_at: date
    closed_at: Optional[date] = None


class LoanCreate(BaseModel):
    loan_id: str
    account_id: str
    principal_amount: Decimal = Field(gt=0)
    annual_interest_rate: Decimal = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    start_date: date
    maturity_date: date
    loan_status: Literal["ACTIVE", "PAID_OFF", "CLOSED", "DEFAULTED"]

class LoanResponse(ORMModel):
    loan_id: str
    account_id: str
    principal_amount: Decimal
    annual_interest_rate: Decimal
    currency: str
    start_date: date
    maturity_date: date
    loan_status: str


class InstallmentCreate(BaseModel):
    installment_id: str
    loan_id: str
    installment_number: int = Field(gt=0)
    due_date: date
    principal_due: Decimal = Field(ge=0)
    interest_due: Decimal = Field(ge=0)
    fees_due: Decimal = Field(default=Decimal("0"), ge=0)
    installment_status: Literal["SCHEDULED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"]

class InstallmentResponse(ORMModel):
    installment_id: str
    loan_id: str
    installment_number: int
    due_date: date
    principal_due: Decimal
    interest_due: Decimal
    fees_due: Decimal
    installment_status: str


class SnapshotCreate(BaseModel):
    loan_id: str
    as_of_date: date
    calculation_version: str = Field(default="v1", min_length=1, max_length=30)

class SnapshotResponse(ORMModel):
    snapshot_id: str
    loan_id: str
    as_of_date: date
    days_past_due: int
    arrears_amount: Decimal
    outstanding_balance: Decimal
    overdue_installment_count: int
    calculation_version: str


class PreferenceCreate(BaseModel):
    preference_id: str
    customer_id: str
    channel: Literal["PHONE", "SMS", "EMAIL", "POST"]
    allowed_weekdays: list[int] = Field(min_length=1, max_length=7)
    window_start: time
    window_end: time
    timezone: str
    opted_out: bool = False
    effective_from: date
    effective_to: Optional[date] = None


class LoanStatusUpdate(BaseModel):
    loan_status: Literal["ACTIVE", "PAID_OFF", "CLOSED", "DEFAULTED"]


class CaseCreate(BaseModel):
    case_id: str
    loan_id: str
    opened_at: datetime
    case_status: Literal["OPEN", "ON_HOLD", "RESOLVED", "CLOSED"] = "OPEN"
    hold_reason: Optional[str] = None

class CaseStatusUpdate(BaseModel):
    new_status: Literal["OPEN", "ON_HOLD", "RESOLVED", "CLOSED"]
    reason: str = Field(min_length=1)
    actor_type: Literal["SYSTEM", "ANALYST", "REVIEWER", "ADMIN"] = "ANALYST"
    actor_id: Optional[str] = None
    hold_reason: Optional[str] = None


class ContactAttemptCreate(BaseModel):
    contact_attempt_id: str
    case_id: str
    channel: Literal["PHONE", "SMS", "EMAIL", "POST"]
    scheduled_at: datetime
    attempted_at: Optional[datetime] = None
    outcome: Optional[Literal["REACHED", "NO_ANSWER", "MESSAGE_SENT", "CUSTOMER_REQUESTED_CALLBACK", "RESTRICTED", "FAILED"]] = None


class PromiseCreate(BaseModel):
    promise_id: str
    case_id: str
    promised_amount: Decimal = Field(gt=0)
    promised_date: date


class PaymentCreate(BaseModel):
    payment_id: str
    account_id: str
    received_at: datetime
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    payment_method: Literal["BANK_TRANSFER", "UPI", "CARD", "CASH", "OTHER"]
    external_reference: Optional[str] = None


class AllocationCreate(BaseModel):
    payment_id: str
    installment_id: str
    allocated_amount: Decimal = Field(gt=0)
    allocation_status: Literal["PROPOSED", "CONFIRMED", "REVERSED"] = "PROPOSED"


class ExceptionCreate(BaseModel):
    exception_id: str
    case_id: Optional[str] = None
    loan_id: Optional[str] = None
    issue_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    exception_status: Literal["OPEN", "UNDER_REVIEW", "RESOLVED", "FALSE_POSITIVE"] = "OPEN"
    details: dict
    resolution_note: Optional[str] = None


class PromisePaymentAllocationCreate(BaseModel):
    promise_allocation_id: str
    promise_id: str
    payment_id: str
    allocated_amount: Decimal = Field(gt=0)
