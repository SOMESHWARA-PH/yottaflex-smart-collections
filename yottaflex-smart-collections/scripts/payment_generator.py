import random
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models as m

SEED = 20261022
AS_OF_DATE = date(2026, 10, 31)
CALCULATION_VERSION = "synthetic-v1"
BATCH_SIZE = 500
PAYMENT_METHODS = ["BANK_TRANSFER", "UPI", "CARD", "CASH", "OTHER"]


def money(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def next_numeric_id(db, column, prefix):
    rows = db.query(column).all()
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    highest = 0
    for row in rows:
        match = pattern.fullmatch(str(row[0]))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def payment_datetime(payment_date):
    return datetime.combine(
        payment_date,
        time(random.randint(9, 18), random.randint(0, 59)),
        tzinfo=timezone.utc,
    )


def generate_payments():
    random.seed(SEED)
    db: Session = SessionLocal()

    try:
        snapshots = (
            db.query(m.DelinquencySnapshot)
            .filter(
                m.DelinquencySnapshot.calculation_version
                == CALCULATION_VERSION
            )
            .all()
        )
        if not snapshots:
            print("No synthetic dataset found. Generate base loans first.")
            return

        loan_ids = [s.loan_id for s in snapshots]

        existing_count = (
            db.query(m.Payment.payment_id)
            .filter(m.Payment.payment_id.like("PMT-SYN-%"))
            .count()
        )
        if existing_count:
            print(f"Synthetic payments already exist: {existing_count}")
            print("Stopped to prevent duplicate generation.")
            return

        loans = (
            db.query(m.Loan)
            .filter(m.Loan.loan_id.in_(loan_ids))
            .all()
        )
        loan_map = {loan.loan_id: loan for loan in loans}
        installments = (
            db.query(m.Installment)
            .filter(m.Installment.loan_id.in_(loan_ids))
            .order_by(
                m.Installment.loan_id,
                m.Installment.installment_number,
            )
            .all()
        )
        snapshot_map = {s.loan_id: s for s in snapshots}

        if len(loan_map) != len(snapshots):
            raise ValueError("Loan and snapshot counts do not match.")

        payment_start = next_numeric_id(
            db, m.Payment.payment_id, "PMT-SYN-"
        )
        print("Starting synthetic payment generation...")
        print(f"Loans: {len(loans)}")
        print(f"Installments: {len(installments)}")

        allocated_by_installment = {}
        payment_batch = []
        allocation_batch = []
        payment_count = 0
        full_count = 0
        partial_count = 0
        missed_count = 0

        for index, installment in enumerate(installments, start=1):
            total_due = money(
                installment.principal_due
                + installment.interest_due
                + installment.fees_due
            )
            allocated = Decimal("0.00")

            if installment.due_date > AS_OF_DATE:
                installment.installment_status = "SCHEDULED"
            else:
                payment_type = random.choices(
                    ["FULL", "PARTIAL", "MISSED"],
                    weights=[45, 30, 25],
                    k=1,
                )[0]

                if payment_type == "MISSED":
                    missed_count += 1
                else:
                    if payment_type == "FULL":
                        allocated = total_due
                        full_count += 1
                    else:
                        pct = Decimal(random.randint(10, 90)) / Decimal("100")
                        allocated = min(money(total_due * pct), total_due)
                        partial_count += 1

                    if allocated <= 0:
                        raise ValueError(
                            f"Invalid payment amount for {installment.installment_id}"
                        )

                    loan = loan_map[installment.loan_id]
                    number = payment_start + payment_count
                    payment_id = f"PMT-SYN-{number:06d}"
                    payment_date = installment.due_date + timedelta(
                        days=random.randint(
                            0, max(0, (AS_OF_DATE - installment.due_date).days)
                        )
                    )
                    timestamp = payment_datetime(payment_date)

                    payment_batch.append(
                        m.Payment(
                            payment_id=payment_id,
                            account_id=loan.account_id,
                            received_at=timestamp,
                            amount=allocated,
                            currency=loan.currency,
                            payment_method=random.choice(PAYMENT_METHODS),
                            external_reference=f"SYN-REF-{number:06d}",
                        )
                    )
                    allocation_batch.append(
                        m.PaymentAllocation(
                            payment_id=payment_id,
                            installment_id=installment.installment_id,
                            allocated_amount=allocated,
                            allocated_at=timestamp,
                            allocation_status="CONFIRMED",
                        )
                    )
                    allocated_by_installment[installment.installment_id] = allocated
                    payment_count += 1

            remaining = money(total_due - allocated)
            if installment.due_date > AS_OF_DATE:
                installment.installment_status = "SCHEDULED"
            elif remaining <= 0:
                installment.installment_status = "PAID"
            elif allocated > 0:
                installment.installment_status = "PARTIALLY_PAID"
            else:
                installment.installment_status = "OVERDUE"

            if index % BATCH_SIZE == 0:
                db.add_all(payment_batch)
                db.flush()
                db.add_all(allocation_batch)
                db.flush()
                payment_batch.clear()
                allocation_batch.clear()
                print(f"Processed {index}/{len(installments)} installments")

        if payment_batch:
            db.add_all(payment_batch)
            db.flush()
        if allocation_batch:
            db.add_all(allocation_batch)
            db.flush()

        # Recalculate each loan's snapshot from installment balances.
        by_loan = {}
        for installment in installments:
            by_loan.setdefault(installment.loan_id, []).append(installment)

        for loan_id, loan_installments in by_loan.items():
            arrears = Decimal("0.00")
            outstanding = Decimal("0.00")
            overdue_count = 0
            overdue_dates = []

            for installment in loan_installments:
                due = money(
                    installment.principal_due
                    + installment.interest_due
                    + installment.fees_due
                )
                paid = allocated_by_installment.get(
                    installment.installment_id, Decimal("0.00")
                )
                remaining = max(Decimal("0.00"), money(due - paid))
                outstanding += remaining

                if installment.due_date <= AS_OF_DATE and remaining > 0:
                    arrears += remaining
                    overdue_count += 1
                    overdue_dates.append(installment.due_date)

            snap = snapshot_map[loan_id]
            snap.days_past_due = (
                (AS_OF_DATE - min(overdue_dates)).days if overdue_dates else 0
            )
            snap.arrears_amount = money(arrears)
            snap.outstanding_balance = money(outstanding)
            snap.overdue_installment_count = overdue_count

        for installment in installments:
            paid = allocated_by_installment.get(
                installment.installment_id, Decimal("0.00")
            )
            due = money(
                installment.principal_due
                + installment.interest_due
                + installment.fees_due
            )
            if paid > due:
                raise ValueError(
                    f"Allocation exceeds installment due: {installment.installment_id}"
                )

        db.commit()
        print("\nPAYMENT GENERATION COMPLETED")
        print(f"Payments generated: {payment_count}")
        print(f"Allocations generated: {payment_count}")
        print(f"Full payments: {full_count}")
        print(f"Partial payments: {partial_count}")
        print(f"Missed installments: {missed_count}")
        print(f"Snapshots recalculated: {len(snapshots)}")
        print(f"Seed: {SEED}; as-of date: {AS_OF_DATE}")

    except Exception:
        db.rollback()
        print("ERROR: payment generation failed; transaction rolled back.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_payments()
