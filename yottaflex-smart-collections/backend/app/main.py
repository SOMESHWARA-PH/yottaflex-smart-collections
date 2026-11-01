from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app import models as m
from app import schemas as s


app = FastAPI(
    title="YottaFlex Smart Collections API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# HEALTH AND ROOT
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "yottaflex-smart-collections",
        "application": "YottaFlex Smart Collections"
    }

@app.get("/api/v1")
def api_root():
    return {
        "message": "Smart Collections Management API",
        "docs": "/docs"
    }


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

def get_or_404(db, model, key, value):
    row = db.query(model).filter(
        getattr(model, key) == value
    ).first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"{model.__tablename__} record not found"
        )

    return row


def confirmed_allocations(db, installment_id, as_of=None):
    q = (
        db.query(
            func.coalesce(
                func.sum(m.PaymentAllocation.allocated_amount),
                0
            )
        )
        .join(
            m.Payment,
            m.Payment.payment_id == m.PaymentAllocation.payment_id
        )
        .filter(
            m.PaymentAllocation.installment_id == installment_id,
            m.PaymentAllocation.allocation_status == "CONFIRMED"
        )
    )

    if as_of is not None:
        cutoff = datetime.combine(
            as_of,
            time.max,
            tzinfo=timezone.utc
        )
        q = q.filter(m.Payment.received_at <= cutoff)

    return Decimal(q.scalar() or 0)


def installment_remaining(db, ins, as_of=None):
    total = (
        Decimal(ins.principal_due or 0)
        + Decimal(ins.interest_due or 0)
        + Decimal(ins.fees_due or 0)
    )

    return max(
        Decimal("0"),
        total - confirmed_allocations(
            db,
            ins.installment_id,
            as_of
        )
    )


def create_case_score(snapshot):
    dpd = min(snapshot.days_past_due, 90) / 90 * 40

    arrears = (
        min(float(snapshot.arrears_amount) / 50000, 1) * 35
    )

    overdue = (
        min(snapshot.overdue_installment_count, 5) / 5 * 25
    )

    score = round(dpd + arrears + overdue, 2)

    band = (
        "HIGH" if score >= 70
        else "MEDIUM" if score >= 35
        else "LOW"
    )

    return Decimal(str(score)), band, {
        "method": "Explainable weighted heuristic v1",
        "components": {
            "dpd_component_max_40": round(dpd, 2),
            "arrears_component_max_35": round(arrears, 2),
            "overdue_component_max_25": round(overdue, 2)
        },
        "total": score,
        "note": (
            "Operational prioritization only; "
            "restrictions and review holds override this score."
        )
    }


# --------------------------------------------------
# CUSTOMERS
# --------------------------------------------------

@app.post(
    "/api/v1/customers",
    response_model=s.CustomerResponse,
    status_code=201
)
def create_customer(
    payload: s.CustomerCreate,
    db: Session = Depends(get_db)
):
    if db.get(m.Customer, payload.customer_id):
        raise HTTPException(409, "Customer ID already exists")

    row = m.Customer(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


@app.get(
    "/api/v1/customers",
    response_model=list[s.CustomerResponse]
)
def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return (
        db.query(m.Customer)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )


@app.get(
    "/api/v1/customers/{customer_id}",
    response_model=s.CustomerResponse
)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db)
):
    return get_or_404(
        db,
        m.Customer,
        "customer_id",
        customer_id
    )


# --------------------------------------------------
# ACCOUNTS
# --------------------------------------------------

@app.post(
    "/api/v1/accounts",
    response_model=s.AccountResponse,
    status_code=201
)
def create_account(
    payload: s.AccountCreate,
    db: Session = Depends(get_db)
):
    get_or_404(
        db,
        m.Customer,
        "customer_id",
        payload.customer_id
    )

    if db.get(m.Account, payload.account_id):
        raise HTTPException(409, "Account ID already exists")

    if payload.closed_at and payload.closed_at < payload.opened_at:
        raise HTTPException(
            422,
            "closed_at cannot be before opened_at"
        )

    row = m.Account(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


@app.get(
    "/api/v1/accounts",
    response_model=list[s.AccountResponse]
)
def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return (
        db.query(m.Account)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )


@app.get(
    "/api/v1/accounts/{account_id}",
    response_model=s.AccountResponse
)
def get_account(
    account_id: str,
    db: Session = Depends(get_db)
):
    return get_or_404(
        db,
        m.Account,
        "account_id",
        account_id
    )


# --------------------------------------------------
# LOANS
# --------------------------------------------------

@app.post(
    "/api/v1/loans",
    response_model=s.LoanResponse,
    status_code=201
)
def create_loan(
    payload: s.LoanCreate,
    db: Session = Depends(get_db)
):
    get_or_404(
        db,
        m.Account,
        "account_id",
        payload.account_id
    )

    if db.get(m.Loan, payload.loan_id):
        raise HTTPException(409, "Loan ID already exists")

    if payload.maturity_date <= payload.start_date:
        raise HTTPException(
            422,
            "Maturity date must be after start date"
        )

    row = m.Loan(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


@app.get(
    "/api/v1/loans",
    response_model=list[s.LoanResponse]
)
def list_loans(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return (
        db.query(m.Loan)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )


@app.get(
    "/api/v1/loans/{loan_id}",
    response_model=s.LoanResponse
)
def get_loan(
    loan_id: str,
    db: Session = Depends(get_db)
):
    return get_or_404(
        db,
        m.Loan,
        "loan_id",
        loan_id
    )


@app.patch(
    "/api/v1/loans/{loan_id}/status",
    response_model=s.LoanResponse
)
def update_loan_status(
    loan_id: str,
    payload: s.LoanStatusUpdate,
    db: Session = Depends(get_db)
):
    row = get_or_404(
        db,
        m.Loan,
        "loan_id",
        loan_id
    )

    row.loan_status = payload.loan_status

    db.commit()
    db.refresh(row)

    return row


# --------------------------------------------------
# INSTALLMENTS
# --------------------------------------------------

@app.post(
    "/api/v1/installments",
    response_model=s.InstallmentResponse,
    status_code=201
)
def create_installment(
    payload: s.InstallmentCreate,
    db: Session = Depends(get_db)
):
    get_or_404(
        db,
        m.Loan,
        "loan_id",
        payload.loan_id
    )

    if db.get(m.Installment, payload.installment_id):
        raise HTTPException(409, "Installment ID already exists")

    duplicate = db.query(m.Installment).filter_by(
        loan_id=payload.loan_id,
        installment_number=payload.installment_number
    ).first()

    if duplicate:
        raise HTTPException(
            409,
            "Installment number already exists for this loan"
        )

    row = m.Installment(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


@app.get(
    "/api/v1/installments",
    response_model=list[s.InstallmentResponse]
)
def list_installments(
    loan_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    q = db.query(m.Installment)

    if loan_id:
        q = q.filter(m.Installment.loan_id == loan_id)

    return (
        q.order_by(m.Installment.due_date)
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )


@app.get(
    "/api/v1/installments/{installment_id}",
    response_model=s.InstallmentResponse
)
def get_installment(
    installment_id: str,
    db: Session = Depends(get_db)
):
    return get_or_404(
        db,
        m.Installment,
        "installment_id",
        installment_id
    )


# --------------------------------------------------
# DELINQUENCY SNAPSHOTS
# --------------------------------------------------

@app.post(
    "/api/v1/snapshots",
    response_model=s.SnapshotResponse,
    status_code=201
)
def create_snapshot(
    payload: s.SnapshotCreate,
    db: Session = Depends(get_db)
):
    loan = get_or_404(
        db,
        m.Loan,
        "loan_id",
        payload.loan_id
    )

    if loan.loan_status in ("PAID_OFF", "CLOSED"):
        dpd = 0
        arrears = Decimal("0")
        outstanding = Decimal("0")
        count = 0

    else:
        installments = (
            db.query(m.Installment)
            .filter_by(loan_id=loan.loan_id)
            .all()
        )

        overdue = []
        outstanding = Decimal("0")

        for ins in installments:
            if ins.installment_status == "CANCELLED":
                continue

            remaining = installment_remaining(
                db,
                ins,
                payload.as_of_date
            )

            if remaining > 0:
                principal_remaining = max(
                    Decimal("0"),
                    Decimal(ins.principal_due)
                    - max(
                        Decimal("0"),
                        Decimal(
                            ins.principal_due
                            + ins.interest_due
                            + ins.fees_due
                        ) - remaining
                    )
                )

                outstanding += principal_remaining

                if ins.due_date <= payload.as_of_date:
                    overdue.append((ins, remaining))

        arrears = sum(
            (amount for _, amount in overdue),
            Decimal("0")
        )

        oldest = min(
            (ins.due_date for ins, _ in overdue),
            default=None
        )

        dpd = (
            max(0, (payload.as_of_date - oldest).days)
            if oldest else 0
        )

        count = len(overdue)

    row = m.DelinquencySnapshot(
        snapshot_id=f"SNP-{uuid4().hex[:24]}",
        loan_id=loan.loan_id,
        as_of_date=payload.as_of_date,
        days_past_due=dpd,
        arrears_amount=arrears,
        outstanding_balance=outstanding,
        overdue_installment_count=count,
        calculation_version=payload.calculation_version
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


@app.get(
    "/api/v1/snapshots",
    response_model=list[s.SnapshotResponse]
)
def list_snapshots(
    loan_id: str | None = None,
    db: Session = Depends(get_db)
):
    q = db.query(m.DelinquencySnapshot)

    if loan_id:
        q = q.filter_by(loan_id=loan_id)

    return (
        q.order_by(m.DelinquencySnapshot.as_of_date.desc())
        .limit(500)
        .all()
    )


# --------------------------------------------------
# CONTACT PREFERENCES
# --------------------------------------------------

@app.post(
    "/api/v1/contact-preferences",
    status_code=201
)
def create_preference(
    payload: s.PreferenceCreate,
    db: Session = Depends(get_db)
):
    get_or_404(
        db,
        m.Customer,
        "customer_id",
        payload.customer_id
    )

    if any(
        day < 0 or day > 6
        for day in payload.allowed_weekdays
    ):
        raise HTTPException(
            422,
            "Weekdays must be 0=Monday through 6=Sunday"
        )

    if payload.window_end <= payload.window_start:
        raise HTTPException(
            422,
            "window_end must be after window_start"
        )

    if (
        payload.effective_to
        and payload.effective_to < payload.effective_from
    ):
        raise HTTPException(
            422,
            "effective_to cannot be before effective_from"
        )

    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Unknown timezone")

    if db.get(m.ContactPreference, payload.preference_id):
        raise HTTPException(409, "Preference ID already exists")

    row = m.ContactPreference(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "preference_id": row.preference_id,
        "customer_id": row.customer_id,
        "channel": row.channel,
        "opted_out": row.opted_out
    }


# --------------------------------------------------
# PAYMENTS
# --------------------------------------------------

@app.post(
    "/api/v1/payments",
    status_code=201
)
def create_payment(
    payload: s.PaymentCreate,
    db: Session = Depends(get_db)
):
    get_or_404(
        db,
        m.Account,
        "account_id",
        payload.account_id
    )

    if payload.received_at.tzinfo is None:
        raise HTTPException(
            422,
            "received_at must include timezone, e.g. +05:30"
        )

    if db.get(m.Payment, payload.payment_id):
        raise HTTPException(409, "Payment ID already exists")

    row = m.Payment(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "payment_id": row.payment_id,
        "account_id": row.account_id,
        "amount": row.amount,
        "currency": row.currency
    }


# --------------------------------------------------
# PAYMENT ALLOCATIONS
# --------------------------------------------------

@app.post(
    "/api/v1/payment-allocations",
    status_code=201
)
def allocate_payment(
    payload: s.AllocationCreate,
    db: Session = Depends(get_db)
):
    payment = get_or_404(
        db,
        m.Payment,
        "payment_id",
        payload.payment_id
    )

    ins = get_or_404(
        db,
        m.Installment,
        "installment_id",
        payload.installment_id
    )

    loan = get_or_404(
        db,
        m.Loan,
        "loan_id",
        ins.loan_id
    )

    if loan.account_id != payment.account_id:
        raise HTTPException(
            422,
            "Payment account does not match the installment loan account"
        )

    if payload.allocation_status == "CONFIRMED":
        already_allocated = Decimal(
            db.query(
                func.coalesce(
                    func.sum(m.PaymentAllocation.allocated_amount),
                    0
                )
            )
            .filter(
                m.PaymentAllocation.payment_id == payment.payment_id,
                m.PaymentAllocation.allocation_status == "CONFIRMED"
            )
            .scalar() or 0
        )

        if already_allocated + payload.allocated_amount > Decimal(payment.amount):
            raise HTTPException(
                422,
                "Confirmed allocations exceed payment amount"
            )

        remaining = installment_remaining(db, ins)

        if payload.allocated_amount > remaining:
            raise HTTPException(
                422,
                "Allocation exceeds installment outstanding amount"
            )

    row = m.PaymentAllocation(**payload.model_dump())

    db.add(row)

    if payload.allocation_status == "CONFIRMED":
        db.flush()

        remaining_after = installment_remaining(db, ins)

        ins.installment_status = (
            "PAID" if remaining_after == 0
            else "PARTIALLY_PAID"
        )

    db.commit()

    return {
        "message": "Allocation recorded",
        "allocation_id": row.allocation_id,
        "status": row.allocation_status
    }


# --------------------------------------------------
# COLLECTION CASES
# --------------------------------------------------

@app.post(
    "/api/v1/cases",
    status_code=201
)
def create_case(
    payload: s.CaseCreate,
    db: Session = Depends(get_db)
):
    loan = get_or_404(
        db,
        m.Loan,
        "loan_id",
        payload.loan_id
    )

    if payload.opened_at.tzinfo is None:
        raise HTTPException(
            422,
            "opened_at must include timezone"
        )

    if db.get(m.CollectionCase, payload.case_id):
        raise HTTPException(409, "Case ID already exists")

    if loan.loan_status in ("PAID_OFF", "CLOSED"):
        raise HTTPException(
            422,
            "Paid-off or closed loans cannot enter collections"
        )

    latest = (
        db.query(m.DelinquencySnapshot)
        .filter_by(loan_id=loan.loan_id)
        .order_by(m.DelinquencySnapshot.as_of_date.desc())
        .first()
    )

    if not latest:
        raise HTTPException(
            422,
            "Create a delinquency snapshot before opening a case"
        )

    if latest.arrears_amount <= 0:
        raise HTTPException(
            422,
            "No arrears; collection case not required"
        )

    score, band, explanation = create_case_score(latest)

    hold_reason = payload.hold_reason
    case_status = payload.case_status

    if hold_reason:
        case_status = "ON_HOLD"

    row = m.CollectionCase(
        case_id=payload.case_id,
        loan_id=loan.loan_id,
        opened_at=payload.opened_at,
        case_status=case_status,
        priority_score=score,
        priority_band=band,
        score_explanation=explanation,
        hold_reason=hold_reason
    )

    db.add(row)
    db.flush()

    db.add(
        m.CollectionCaseEvent(
            case_id=row.case_id,
            previous_status=None,
            new_status=case_status,
            event_type="CASE_CREATED",
            actor_type="SYSTEM",
            reason="Case created from latest delinquency snapshot",
            event_metadata={
                "priority_score": float(score),
                "priority_band": band
            }
        )
    )

    db.commit()

    return {
        "case_id": row.case_id,
        "loan_id": row.loan_id,
        "case_status": row.case_status,
        "priority_score": row.priority_score,
        "priority_band": row.priority_band,
        "score_explanation": row.score_explanation
    }


@app.get("/api/v1/cases")
def list_cases(
    case_status: str | None = None,
    db: Session = Depends(get_db)
):
    q = db.query(m.CollectionCase)

    if case_status:
        q = q.filter_by(case_status=case_status)

    return (
        q.order_by(m.CollectionCase.priority_score.desc())
        .limit(500)
        .all()
    )


@app.patch("/api/v1/cases/{case_id}/status")
def update_case_status(
    case_id: str,
    payload: s.CaseStatusUpdate,
    db: Session = Depends(get_db)
):
    row = get_or_404(
        db,
        m.CollectionCase,
        "case_id",
        case_id
    )

    previous = row.case_status

    row.case_status = payload.new_status

    row.hold_reason = (
        payload.hold_reason
        if payload.new_status == "ON_HOLD"
        else None
    )

    if payload.new_status in ("RESOLVED", "CLOSED"):
        row.resolved_at = datetime.now(timezone.utc)
    else:
        row.resolved_at = None

    db.add(
        m.CollectionCaseEvent(
            case_id=row.case_id,
            previous_status=previous,
            new_status=row.case_status,
            event_type="STATUS_CHANGED",
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            reason=payload.reason,
            event_metadata={
                "hold_reason": row.hold_reason
            }
        )
    )

    db.commit()

    return {
        "case_id": row.case_id,
        "previous_status": previous,
        "new_status": row.case_status
    }


# --------------------------------------------------
# CONTACT ATTEMPTS
# --------------------------------------------------

@app.post(
    "/api/v1/contact-attempts",
    status_code=201
)
def schedule_contact(
    payload: s.ContactAttemptCreate,
    db: Session = Depends(get_db)
):
    case = get_or_404(
        db,
        m.CollectionCase,
        "case_id",
        payload.case_id
    )

    loan = get_or_404(
        db,
        m.Loan,
        "loan_id",
        case.loan_id
    )

    account = get_or_404(
        db,
        m.Account,
        "account_id",
        loan.account_id
    )

    if payload.scheduled_at.tzinfo is None:
        raise HTTPException(
            422,
            "scheduled_at must include timezone"
        )

    if case.case_status != "OPEN":
        raise HTTPException(
            422,
            "Only OPEN cases can be contacted"
        )

    if loan.loan_status in ("PAID_OFF", "CLOSED"):
        raise HTTPException(
            422,
            "Paid-off/closed loans cannot be contacted"
        )

    prefs = (
        db.query(m.ContactPreference)
        .filter(
            m.ContactPreference.customer_id == account.customer_id,
            m.ContactPreference.channel == payload.channel,
            m.ContactPreference.effective_from <= payload.scheduled_at.date(),
            (
                m.ContactPreference.effective_to.is_(None)
                | (
                    m.ContactPreference.effective_to
                    >= payload.scheduled_at.date()
                )
            )
        )
        .order_by(
            m.ContactPreference.effective_from.desc()
        )
        .all()
    )

    details = {
        "checks": [],
        "weekday_convention": "0=Monday, 6=Sunday"
    }

    allowed = bool(prefs)

    if not prefs:
        details["checks"].append(
            "No active contact preference: blocked by safe default"
        )

    else:
        pref = prefs[0]

        if pref.opted_out:
            allowed = False
            details["checks"].append("Customer opted out")

        local_dt = payload.scheduled_at.astimezone(
            ZoneInfo(pref.timezone)
        )

        if local_dt.weekday() not in pref.allowed_weekdays:
            allowed = False
            details["checks"].append("Weekday not permitted")

        local_time = local_dt.time().replace(tzinfo=None)

        if not (
            pref.window_start <= local_time <= pref.window_end
        ):
            allowed = False
            details["checks"].append(
                "Outside permitted contact window"
            )

        recent_count = (
            db.query(m.ContactAttempt)
            .filter(
                m.ContactAttempt.customer_id == account.customer_id,
                m.ContactAttempt.scheduled_at
                >= payload.scheduled_at - timedelta(days=7),
                m.ContactAttempt.scheduled_at
                <= payload.scheduled_at,
                m.ContactAttempt.restriction_check_passed.is_(True)
            )
            .count()
        )

        if recent_count >= 3:
            allowed = False
            details["checks"].append(
                "Frequency cap reached: maximum 3 permitted attempts in rolling 7 days"
            )

        details["preference_id"] = pref.preference_id
        details["timezone"] = pref.timezone

    if db.get(
        m.ContactAttempt,
        payload.contact_attempt_id
    ):
        raise HTTPException(
            409,
            "Contact attempt ID already exists"
        )

    row = m.ContactAttempt(
        contact_attempt_id=payload.contact_attempt_id,
        case_id=case.case_id,
        customer_id=account.customer_id,
        channel=payload.channel,
        scheduled_at=payload.scheduled_at,
        attempted_at=payload.attempted_at,
        outcome=payload.outcome if allowed else "RESTRICTED",
        restriction_check_passed=allowed,
        restriction_check_details=details
    )

    db.add(row)
    db.commit()

    return {
        "contact_attempt_id": row.contact_attempt_id,
        "permitted": allowed,
        "outcome": row.outcome,
        "restriction_details": details
    }


# --------------------------------------------------
# PROMISE TO PAY
# --------------------------------------------------

@app.post(
    "/api/v1/promises",
    status_code=201
)
def create_promise(
    payload: s.PromiseCreate,
    db: Session = Depends(get_db)
):
    case = get_or_404(
        db,
        m.CollectionCase,
        "case_id",
        payload.case_id
    )

    latest = (
        db.query(m.DelinquencySnapshot)
        .filter_by(loan_id=case.loan_id)
        .order_by(m.DelinquencySnapshot.as_of_date.desc())
        .first()
    )

    if not latest:
        raise HTTPException(
            422,
            "A delinquency snapshot is required"
        )

    if payload.promised_amount > Decimal(latest.arrears_amount):
        raise HTTPException(
            422,
            "Promise amount cannot exceed latest arrears"
        )

    if db.get(m.PromiseToPay, payload.promise_id):
        raise HTTPException(409, "Promise ID already exists")

    row = m.PromiseToPay(
        promise_id=payload.promise_id,
        case_id=case.case_id,
        promised_amount=payload.promised_amount,
        promised_date=payload.promised_date,
        promise_status="PENDING"
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "promise_id": row.promise_id,
        "promise_status": row.promise_status
    }


# --------------------------------------------------
# PROMISE PAYMENT ALLOCATIONS
# --------------------------------------------------

@app.post(
    "/api/v1/promise-payment-allocations",
    status_code=201
)
def allocate_payment_to_promise(
    payload: s.PromisePaymentAllocationCreate,
    db: Session = Depends(get_db)
):
    promise = get_or_404(
        db,
        m.PromiseToPay,
        "promise_id",
        payload.promise_id
    )

    payment = get_or_404(
        db,
        m.Payment,
        "payment_id",
        payload.payment_id
    )

    if db.get(
        m.PromisePaymentAllocation,
        payload.promise_allocation_id
    ):
        raise HTTPException(
            409,
            "Promise allocation ID already exists"
        )

    duplicate = (
        db.query(m.PromisePaymentAllocation)
        .filter_by(
            promise_id=payload.promise_id,
            payment_id=payload.payment_id
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            409,
            "This payment is already linked to this promise"
        )

    if promise.promise_status != "PENDING":
        raise HTTPException(
            422,
            "Only pending promises can receive payment allocations"
        )

    case = get_or_404(
        db,
        m.CollectionCase,
        "case_id",
        promise.case_id
    )

    loan = get_or_404(
        db,
        m.Loan,
        "loan_id",
        case.loan_id
    )

    if payment.account_id != loan.account_id:
        raise HTTPException(
            422,
            "Payment does not belong to the promise loan account"
        )

    due_cutoff = datetime.combine(
        promise.promised_date,
        time.max,
        tzinfo=timezone.utc
    )

    if payment.received_at > due_cutoff:
        raise HTTPException(
            422,
            "Payment was received after the promised date"
        )

    confirmed_amount = Decimal(
        db.query(
            func.coalesce(
                func.sum(m.PaymentAllocation.allocated_amount),
                0
            )
        )
        .filter(
            m.PaymentAllocation.payment_id == payment.payment_id,
            m.PaymentAllocation.allocation_status == "CONFIRMED"
        )
        .scalar() or 0
    )

    if confirmed_amount <= 0:
        raise HTTPException(
            422,
            "Payment has no confirmed installment allocation"
        )

    already_linked_payment = Decimal(
        db.query(
            func.coalesce(
                func.sum(
                    m.PromisePaymentAllocation.allocated_amount
                ),
                0
            )
        )
        .filter(
            m.PromisePaymentAllocation.payment_id
            == payment.payment_id
        )
        .scalar() or 0
    )

    if (
        already_linked_payment + payload.allocated_amount
        > confirmed_amount
    ):
        raise HTTPException(
            422,
            "Promise allocations exceed confirmed payment amount"
        )

    already_linked_promise = Decimal(
        db.query(
            func.coalesce(
                func.sum(
                    m.PromisePaymentAllocation.allocated_amount
                ),
                0
            )
        )
        .filter(
            m.PromisePaymentAllocation.promise_id
            == promise.promise_id
        )
        .scalar() or 0
    )

    if (
        already_linked_promise + payload.allocated_amount
        > Decimal(promise.promised_amount)
    ):
        raise HTTPException(
            422,
            "Allocations exceed promised amount"
        )

    row = m.PromisePaymentAllocation(
        promise_allocation_id=payload.promise_allocation_id,
        promise_id=payload.promise_id,
        payment_id=payload.payment_id,
        allocated_amount=payload.allocated_amount
    )

    try:
        db.add(row)
        db.commit()
        db.refresh(row)

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Payment linked to promise successfully",
        "promise_allocation_id": row.promise_allocation_id,
        "promise_id": row.promise_id,
        "payment_id": row.payment_id,
        "allocated_amount": float(row.allocated_amount)
    }


# --------------------------------------------------
# PROMISE RECONCILIATION
# --------------------------------------------------

@app.post("/api/v1/promises/reconcile")
def reconcile_promises(
    db: Session = Depends(get_db)
):
    today = date.today()

    rows = (
        db.query(m.PromiseToPay)
        .filter(
            m.PromiseToPay.promise_status == "PENDING",
            m.PromiseToPay.promised_date <= today
        )
        .order_by(m.PromiseToPay.promised_date)
        .all()
    )

    updated = []

    try:
        for promise in rows:
            due_cutoff = datetime.combine(
                promise.promised_date,
                time.max,
                tzinfo=timezone.utc
            )

            paid_amount = (
                db.query(
                    func.coalesce(
                        func.sum(
                            m.PromisePaymentAllocation.allocated_amount
                        ),
                        0
                    )
                )
                .join(
                    m.Payment,
                    m.Payment.payment_id
                    == m.PromisePaymentAllocation.payment_id
                )
                .filter(
                    m.PromisePaymentAllocation.promise_id
                    == promise.promise_id,
                    m.Payment.received_at <= due_cutoff
                )
                .scalar()
            )

            paid_amount = Decimal(paid_amount or 0)

            if paid_amount >= Decimal(promise.promised_amount):
                new_status = "FULFILLED"

            elif paid_amount > 0:
                new_status = "PARTIALLY_FULFILLED"

            else:
                new_status = "MISSED"

            promise.promise_status = new_status

            updated.append({
                "promise_id": promise.promise_id,
                "promised_amount": float(promise.promised_amount),
                "paid_amount": float(paid_amount),
                "status": new_status
            })

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "as_of_date": today.isoformat(),
        "updated_count": len(updated),
        "results": updated
    }


# --------------------------------------------------
# EXCEPTIONS
# --------------------------------------------------

@app.post(
    "/api/v1/exceptions",
    status_code=201
)
def create_exception(
    payload: s.ExceptionCreate,
    db: Session = Depends(get_db)
):
    if payload.case_id:
        get_or_404(
            db,
            m.CollectionCase,
            "case_id",
            payload.case_id
        )

    if payload.loan_id:
        get_or_404(
            db,
            m.Loan,
            "loan_id",
            payload.loan_id
        )

    if not payload.case_id and not payload.loan_id:
        raise HTTPException(
            422,
            "case_id or loan_id is required"
        )

    if db.get(m.ExceptionRecord, payload.exception_id):
        raise HTTPException(
            409,
            "Exception ID already exists"
        )

    row = m.ExceptionRecord(**payload.model_dump())

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "exception_id": row.exception_id,
        "issue_type": row.issue_type,
        "status": row.exception_status
    }


@app.get("/api/v1/exceptions")
def list_exceptions(
    exception_status: str | None = None,
    db: Session = Depends(get_db)
):
    q = db.query(m.ExceptionRecord)

    if exception_status:
        q = q.filter_by(
            exception_status=exception_status
        )

    return (
        q.order_by(m.ExceptionRecord.detected_at.desc())
        .limit(500)
        .all()
    )


# --------------------------------------------------
# DASHBOARD SUMMARY
# --------------------------------------------------

@app.get("/api/v1/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db)
):
    return {
        "customers": db.query(m.Customer).count(),
        "accounts": db.query(m.Account).count(),
        "loans": db.query(m.Loan).count(),
        "installments": db.query(m.Installment).count(),

        "open_cases": (
            db.query(m.CollectionCase)
            .filter(
                m.CollectionCase.case_status == "OPEN"
            )
            .count()
        ),

        "on_hold_cases": (
            db.query(m.CollectionCase)
            .filter(
                m.CollectionCase.case_status == "ON_HOLD"
            )
            .count()
        ),

        "open_exceptions": (
            db.query(m.ExceptionRecord)
            .filter(
                m.ExceptionRecord.exception_status == "OPEN"
            )
            .count()
        ),

        "payments": db.query(m.Payment).count()
    }