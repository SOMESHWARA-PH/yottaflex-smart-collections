import pytest
from pydantic import ValidationError
from app.schemas import PaymentCreate, AllocationCreate, LoanStatusUpdate

def test_payment_amount_must_be_positive():
    with pytest.raises(ValidationError):
        PaymentCreate(payment_id='P1', account_id='A1', received_at='2026-11-01T10:00:00Z', amount=0, currency='INR', payment_method='UPI')

def test_allocation_amount_must_be_positive():
    with pytest.raises(ValidationError):
        AllocationCreate(payment_id='P1', installment_id='I1', allocated_amount=0)

def test_loan_status_enum():
    assert LoanStatusUpdate(loan_status='PAID_OFF').loan_status == 'PAID_OFF'
    with pytest.raises(ValidationError):
        LoanStatusUpdate(loan_status='UNKNOWN')
