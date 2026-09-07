import time

from app.database import SessionLocal
from app.models import Payment
from app.services.payment_processor import retry_payment


def process_pending_payments():
    db = SessionLocal()

    try:
        payments = (
            db.query(Payment)
            .filter(
                Payment.status.in_(["PENDING", "FAILED"])
            )
            .all()
        )

        for payment in payments:
            retry_payment(db, payment)

    finally:
        db.close()


def run_worker():
    print("Payment worker started...")

    while True:
        try:
            process_pending_payments()
        except Exception as exc:
            print(f"Worker error: {exc}")

        time.sleep(5)


if __name__ == "__main__":
    run_worker()