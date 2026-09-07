from datetime import datetime
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database import Base, engine, get_db
from app.models import Payment, PaymentEvent, User
from app.schemas import LoginRequest, PaymentCreate


# =========================================================
# APPLICATION
# =========================================================

app = FastAPI(
    title="Event-Driven Payment Processing System",
    description=(
        "Payment processing API with authentication, "
        "idempotency, retry handling and event tracking."
    ),
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# AUTHENTICATION
# =========================================================

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    username = decode_access_token(
        credentials.credentials
    )

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# =========================================================
# DEFAULT ADMIN USER
# =========================================================

def create_default_user():

    db = next(get_db())

    try:

        existing_user = (
            db.query(User)
            .filter(User.username == "admin")
            .first()
        )

        if not existing_user:

            user = User(
                username="admin",
                password_hash=hash_password(
                    "admin123"
                ),
            )

            db.add(user)
            db.commit()

    finally:

        db.close()


create_default_user()


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "message": "Event-Driven Payment Processing System",
        "status": "running",
        "version": "1.0.0",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "payment-api",
    }


# =========================================================
# LOGIN
# =========================================================

@app.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):

    user = (
        db.query(User)
        .filter(
            User.username == request.username
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    password_valid = verify_password(
        request.password,
        user.password_hash,
    )

    if not password_valid:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        user.username
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


# =========================================================
# CREATE PAYMENT
# =========================================================

@app.post("/payments")
def create_payment(
    request: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # -----------------------------------------------------
    # VALIDATE AMOUNT
    # -----------------------------------------------------

    if request.amount <= 0:

        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero",
        )


    # -----------------------------------------------------
    # NORMALIZE CURRENCY
    # -----------------------------------------------------

    currency = request.currency.upper().strip()

    allowed_currencies = {
        "USD",
        "EUR",
        "GBP",
        "INR",
    }

    if currency not in allowed_currencies:

        raise HTTPException(
            status_code=400,
            detail="Unsupported currency",
        )


    # -----------------------------------------------------
    # VALIDATE IDEMPOTENCY KEY
    # -----------------------------------------------------

    idempotency_key = (
        request.idempotency_key.strip()
    )

    if not idempotency_key:

        raise HTTPException(
            status_code=400,
            detail="Idempotency key is required",
        )


    # -----------------------------------------------------
    # IDEMPOTENCY CHECK
    # -----------------------------------------------------

    existing_payment = (
        db.query(Payment)
        .filter(
            Payment.idempotency_key
            == idempotency_key
        )
        .first()
    )

    if existing_payment:

        # Return the original transaction.
        # This is the idempotency behavior.
        return existing_payment


    # -----------------------------------------------------
    # GENERATE PUBLIC PAYMENT ID
    # -----------------------------------------------------

    payment_id = (
        "PAY-"
        + uuid.uuid4()
        .hex[:16]
        .upper()
    )


    # -----------------------------------------------------
    # INITIAL PAYMENT STATE
    # -----------------------------------------------------

    # Normal transaction:
    # PENDING -> PROCESSING -> COMPLETED
    #
    # Failure test:
    # PENDING -> PROCESSING -> FAILED
    #
    # To test failure, use:
    # failure-test-001
    # failure-test-002
    # etc.

    is_failure_test = (
        idempotency_key
        .lower()
        .startswith("failure-test-")
    )


    # -----------------------------------------------------
    # CREATE PAYMENT
    # -----------------------------------------------------

    payment = Payment(
        payment_id=payment_id,
        user_id=current_user.id,
        amount=request.amount,
        currency=currency,
        status="PENDING",
        idempotency_key=idempotency_key,
        retry_count=0,
        failure_reason=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(payment)

    # Flush gives us payment.id before commit.
    db.flush()


    # -----------------------------------------------------
    # CREATED EVENT
    # -----------------------------------------------------

    created_event = PaymentEvent(
        payment_id=payment.id,
        event_type="PAYMENT_CREATED",
        message="Payment created successfully.",
        created_at=datetime.utcnow(),
    )

    db.add(created_event)


    # -----------------------------------------------------
    # PROCESSING EVENT
    # -----------------------------------------------------

    payment.status = "PROCESSING"
    payment.updated_at = datetime.utcnow()

    processing_event = PaymentEvent(
        payment_id=payment.id,
        event_type="PAYMENT_PROCESSING",
        message="Payment entered processing.",
        created_at=datetime.utcnow(),
    )

    db.add(processing_event)


    # -----------------------------------------------------
    # SIMULATED RESULT
    # -----------------------------------------------------

    if is_failure_test:

        payment.status = "FAILED"
        payment.failure_reason = (
            "Simulated payment processing failure."
        )
        payment.updated_at = datetime.utcnow()

        failed_event = PaymentEvent(
            payment_id=payment.id,
            event_type="PAYMENT_FAILED",
            message=(
                "Payment processing failed "
                "during the simulated failure test."
            ),
            created_at=datetime.utcnow(),
        )

        db.add(failed_event)

    else:

        payment.status = "COMPLETED"
        payment.failure_reason = None
        payment.updated_at = datetime.utcnow()

        completed_event = PaymentEvent(
            payment_id=payment.id,
            event_type="PAYMENT_COMPLETED",
            message="Payment completed successfully.",
            created_at=datetime.utcnow(),
        )

        db.add(completed_event)


    # -----------------------------------------------------
    # COMMIT
    # -----------------------------------------------------

    db.commit()
    db.refresh(payment)

    return payment


# =========================================================
# RETRY PAYMENT
# =========================================================

@app.post("/payments/{payment_id}/retry")
def retry_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # -----------------------------------------------------
    # FIND PAYMENT
    # -----------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.payment_id
            == payment_id
        )
        .first()
    )

    if not payment:

        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )


    # -----------------------------------------------------
    # SECURITY
    # -----------------------------------------------------

    if payment.user_id != current_user.id:

        raise HTTPException(
            status_code=403,
            detail="You cannot retry this payment",
        )


    # -----------------------------------------------------
    # ONLY FAILED PAYMENTS CAN RETRY
    # -----------------------------------------------------

    if payment.status not in [
        "FAILED",
        "PERMANENTLY_FAILED",
    ]:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only failed payments "
                "can be retried"
            ),
        )


    # -----------------------------------------------------
    # MAXIMUM RETRIES
    # -----------------------------------------------------

    MAX_RETRIES = 3

    if payment.retry_count >= MAX_RETRIES:

        payment.status = "PERMANENTLY_FAILED"
        payment.updated_at = datetime.utcnow()

        event = PaymentEvent(
            payment_id=payment.id,
            event_type="PAYMENT_PERMANENTLY_FAILED",
            message=(
                "Maximum retry attempts reached."
            ),
            created_at=datetime.utcnow(),
        )

        db.add(event)
        db.commit()
        db.refresh(payment)

        return payment


    # -----------------------------------------------------
    # START RETRY
    # -----------------------------------------------------

    payment.retry_count += 1
    payment.status = "PROCESSING"
    payment.failure_reason = None
    payment.updated_at = datetime.utcnow()

    retry_event = PaymentEvent(
        payment_id=payment.id,
        event_type="PAYMENT_RETRY",
        message=(
            f"Payment retry attempt "
            f"{payment.retry_count} started."
        ),
        created_at=datetime.utcnow(),
    )

    db.add(retry_event)


    # -----------------------------------------------------
    # SIMULATE SUCCESS
    # -----------------------------------------------------

    payment.status = "COMPLETED"
    payment.updated_at = datetime.utcnow()

    completed_event = PaymentEvent(
        payment_id=payment.id,
        event_type="PAYMENT_COMPLETED",
        message=(
            "Payment completed successfully "
            "after retry."
        ),
        created_at=datetime.utcnow(),
    )

    db.add(completed_event)

    db.commit()
    db.refresh(payment)

    return payment


# =========================================================
# GET ALL PAYMENTS
# =========================================================

@app.get("/payments")
def get_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    payments = (
        db.query(Payment)
        .filter(
            Payment.user_id
            == current_user.id
        )
        .order_by(
            Payment.id.desc()
        )
        .all()
    )

    return payments


# =========================================================
# GET SINGLE PAYMENT
# =========================================================

@app.get("/payments/{payment_id}")
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.payment_id
            == payment_id
        )
        .first()
    )

    if not payment:

        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )


    if payment.user_id != current_user.id:

        raise HTTPException(
            status_code=403,
            detail="You cannot access this payment",
        )


    return payment


# =========================================================
# GET PAYMENT EVENTS
# =========================================================

@app.get("/payments/{payment_id}/events")
def get_payment_events(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # -----------------------------------------------------
    # FIND PAYMENT
    # -----------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.payment_id
            == payment_id
        )
        .first()
    )

    if not payment:

        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )


    # -----------------------------------------------------
    # SECURITY
    # -----------------------------------------------------

    if payment.user_id != current_user.id:

        raise HTTPException(
            status_code=403,
            detail="You cannot access these events",
        )


    # -----------------------------------------------------
    # GET EVENTS
    # -----------------------------------------------------

    events = (
        db.query(PaymentEvent)
        .filter(
            PaymentEvent.payment_id
            == payment.id
        )
        .order_by(
            PaymentEvent.id.asc()
        )
        .all()
    )

    return events


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    payments = (
        db.query(Payment)
        .filter(
            Payment.user_id
            == current_user.id
        )
        .all()
    )


    total_payments = len(payments)


    completed_payments = sum(
        1
        for payment in payments
        if payment.status
        == "COMPLETED"
    )


    failed_payments = sum(
        1
        for payment in payments
        if payment.status
        in [
            "FAILED",
            "PERMANENTLY_FAILED",
        ]
    )


    pending_payments = sum(
        1
        for payment in payments
        if payment.status
        in [
            "PENDING",
            "PROCESSING",
        ]
    )


    total_amount = sum(
        float(payment.amount)
        for payment in payments
    )


    return {
        "total_payments": total_payments,
        "completed_payments": completed_payments,
        "failed_payments": failed_payments,
        "pending_payments": pending_payments,
        "total_amount": total_amount,
    }

