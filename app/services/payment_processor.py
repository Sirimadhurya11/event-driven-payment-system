import random
import time

from sqlalchemy.orm import Session

from app.models import Payment, PaymentEvent


MAX_RETRIES = 3


def add_event(
    db: Session,
    payment_id: str,
    event_type: str,
    message: str,
):
    event = PaymentEvent(
        payment_id=payment_id,
        event_type=event_type,
        message=message,
    )

    db.add(event)
    db.commit()


def process_payment(db: Session, payment: Payment) -> Payment:
    payment.status = "PROCESSING"
    db.commit()

    add_event(
        db,
        payment.payment_id,
        "PAYMENT_PROCESSING",
        "Payment processing started",
    )

    # Simulate an external payment provider.
    time.sleep(1)

    # Simulated success/failure for our local project.
    successful = random.random() >= 0.20

    if successful:
        payment.status = "COMPLETED"
        payment.failure_reason = None
        db.commit()

        add_event(
            db,
            payment.payment_id,
            "PAYMENT_COMPLETED",
            "Payment completed successfully",
        )

    else:
        payment.status = "FAILED"
        payment.retry_count += 1
        payment.failure_reason = "Payment provider temporarily unavailable"
        db.commit()

        add_event(
            db,
            payment.payment_id,
            "PAYMENT_FAILED",
            payment.failure_reason,
        )

    return payment


def retry_payment(db: Session, payment: Payment) -> Payment:
    if payment.status == "COMPLETED":
        return payment

    if payment.retry_count >= MAX_RETRIES:
        payment.status = "PERMANENTLY_FAILED"
        payment.failure_reason = "Maximum retry attempts exceeded"
        db.commit()

        add_event(
            db,
            payment.payment_id,
            "PAYMENT_PERMANENTLY_FAILED",
            payment.failure_reason,
        )

        return payment

    return process_payment(db, payment)