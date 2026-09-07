from pydantic import BaseModel, Field, field_validator


# =========================================================
# LOGIN
# =========================================================

class LoginRequest(BaseModel):

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    password: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Username cannot be empty"
            )

        return value


# =========================================================
# CREATE PAYMENT
# =========================================================

class PaymentCreate(BaseModel):

    amount: float = Field(
        ...,
        gt=0,
        description="Payment amount must be greater than zero",
    )

    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Supported currency code",
    )

    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique key used to prevent duplicate payments",
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value):

        value = value.strip().upper()

        allowed_currencies = {
            "USD",
            "EUR",
            "GBP",
            "INR",
        }

        if value not in allowed_currencies:
            raise ValueError(
                "Currency must be USD, EUR, GBP or INR"
            )

        return value


    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Idempotency key cannot be empty"
            )

        return value
