import uuid

from sqlalchemy.orm import Session

from app.models import Payment
from app.schemas import PaymentCreate
from app.services.payment_processor import process_payment


def generate_payment_id() -> str:
    return f"PAY-{uuid.uuid4().hex[:16].upper()}"


def create_payment(
    db: Session,
    user_id: int,
    data: PaymentCreate,
) -> Payment:

    existing_payment = (
        db.query(Payment)
        .filter(
            Payment.idempotency_key == data.idempotency_key
        )
        .first()
    )

    if existing_payment:
        return existing_payment

    payment = Payment(
        payment_id=generate_payment_id(),
        user_id=user_id,
        amount=data.amount,
        currency=data.currency.upper(),
        status="PENDING",
        idempotency_key=data.idempotency_key,
        retry_count=0,
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment


def process_created_payment(
    db: Session,
    payment: Payment,
) -> Payment:
    return process_payment(db, payment)