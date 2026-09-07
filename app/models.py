from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


# =========================================================
# USER
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # One user can have many payments
    payments = relationship(
        "Payment",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# =========================================================
# PAYMENT
# =========================================================

class Payment(Base):
    __tablename__ = "payments"

    # Internal database ID
    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Public payment ID
    # Example: PAY-A1B2C3D4E5F6
    payment_id = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # Owner of payment
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    amount = Column(
        Float,
        nullable=False,
    )

    currency = Column(
        String(10),
        nullable=False,
    )

    # Possible values:
    #
    # PENDING
    # PROCESSING
    # COMPLETED
    # FAILED
    # PERMANENTLY_FAILED
    status = Column(
        String(30),
        default="PENDING",
        nullable=False,
        index=True,
    )

    # Prevent duplicate payment creation
    idempotency_key = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Number of retry attempts
    retry_count = Column(
        Integer,
        default=0,
        nullable=False,
    )

    # Failure information
    failure_reason = Column(
        String(500),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships

    user = relationship(
        "User",
        back_populates="payments",
    )

    events = relationship(
        "PaymentEvent",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentEvent.id",
    )


# =========================================================
# PAYMENT EVENT
# =========================================================

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # IMPORTANT:
    # This stores the internal Payment.id
    payment_id = Column(
        Integer,
        ForeignKey("payments.id"),
        nullable=False,
        index=True,
    )

    event_type = Column(
        String(100),
        nullable=False,
    )

    message = Column(
        String(500),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    payment = relationship(
        "Payment",
        back_populates="events",
    )

