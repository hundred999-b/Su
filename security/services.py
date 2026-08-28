import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import (
    RecoveryCode,
    SecurityEvent,
    SecurityOTP,
    SecurityProfile,
)


PIN_MAX_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15
OTP_MAX_ATTEMPTS = 5
OTP_MINUTES = 10
RECOVERY_CODE_COUNT = 20


def get_security_profile(user):
    profile, _ = SecurityProfile.objects.get_or_create(user=user)
    return profile


def set_pin(user, pin):
    pin = str(pin).strip()

    if not pin.isdigit():
        raise ValueError("PIN must contain digits only.")

    if len(pin) < 6 or len(pin) > 12:
        raise ValueError("PIN must contain 6 to 12 digits.")

    profile = get_security_profile(user)
    profile.pin_hash = make_password(pin)
    profile.pin_enabled = True
    profile.failed_pin_attempts = 0
    profile.pin_locked_until = None
    profile.save(
        update_fields=[
            "pin_hash",
            "pin_enabled",
            "failed_pin_attempts",
            "pin_locked_until",
            "updated_at",
        ]
    )

    SecurityEvent.objects.create(
        user=user,
        event_type="PIN_SET",
        success=True,
    )


def disable_pin(user):
    profile = get_security_profile(user)

    profile.pin_enabled = False
    profile.pin_hash = ""
    profile.failed_pin_attempts = 0
    profile.pin_locked_until = None

    profile.save(
        update_fields=[
            "pin_enabled",
            "pin_hash",
            "failed_pin_attempts",
            "pin_locked_until",
            "updated_at",
        ]
    )

    SecurityEvent.objects.create(
        user=user,
        event_type="PIN_DISABLED",
        success=True,
    )


@transaction.atomic
def verify_pin(user, pin):
    profile = SecurityProfile.objects.select_for_update().get(
        user=user
    )

    now = timezone.now()

    if not profile.pin_enabled or not profile.pin_hash:
        raise ValueError("PIN is not enabled.")

    if profile.pin_locked_until and now < profile.pin_locked_until:
        raise ValueError("PIN temporarily locked.")

    if check_password(str(pin), profile.pin_hash):
        profile.failed_pin_attempts = 0
        profile.pin_locked_until = None
        profile.save(
            update_fields=[
                "failed_pin_attempts",
                "pin_locked_until",
                "updated_at",
            ]
        )

        SecurityEvent.objects.create(
            user=user,
            event_type="PIN_VERIFIED",
            success=True,
        )

        return True

    profile.failed_pin_attempts += 1

    if profile.failed_pin_attempts >= PIN_MAX_ATTEMPTS:
        profile.pin_locked_until = now + timedelta(
            minutes=PIN_LOCK_MINUTES
        )
        profile.failed_pin_attempts = 0

    profile.save(
        update_fields=[
            "failed_pin_attempts",
            "pin_locked_until",
            "updated_at",
        ]
    )

    SecurityEvent.objects.create(
        user=user,
        event_type="PIN_VERIFICATION_FAILED",
        success=False,
    )

    return False


def _hash_recovery_code(code):
    return hashlib.sha256(
        code.encode("utf-8")
    ).hexdigest()


@transaction.atomic
def generate_recovery_codes(user, count=RECOVERY_CODE_COUNT):
    if count < 11:
        raise ValueError("Recovery code count must be greater than 10.")

    RecoveryCode.objects.filter(
        user=user,
        used=False,
    ).update(used=True, used_at=timezone.now())

    plain_codes = []

    for _ in range(count):
        code = secrets.token_hex(8).upper()

        RecoveryCode.objects.create(
            user=user,
            code_hash=_hash_recovery_code(code),
        )

        plain_codes.append(code)

    SecurityEvent.objects.create(
        user=user,
        event_type="RECOVERY_CODES_GENERATED",
        success=True,
        metadata={"count": count},
    )

    return plain_codes


@transaction.atomic
def consume_recovery_code(user, code):
    code_hash = _hash_recovery_code(str(code).strip().upper())

    recovery = (
        RecoveryCode.objects
        .select_for_update()
        .filter(
            user=user,
            code_hash=code_hash,
            used=False,
        )
        .first()
    )

    if not recovery:
        SecurityEvent.objects.create(
            user=user,
            event_type="RECOVERY_CODE_FAILED",
            success=False,
        )
        return False

    recovery.used = True
    recovery.used_at = timezone.now()
    recovery.save(update_fields=["used", "used_at"])

    SecurityEvent.objects.create(
        user=user,
        event_type="RECOVERY_CODE_USED",
        success=True,
    )

    return True


def create_otp(user, purpose):
    code = f"{secrets.randbelow(1_000_000):06d}"

    SecurityOTP.objects.filter(
        user=user,
        purpose=purpose,
        used=False,
    ).update(used=True, used_at=timezone.now())

    otp = SecurityOTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=OTP_MINUTES),
    )

    return otp, code


@transaction.atomic
def verify_otp(user, purpose, code):
    otp = (
        SecurityOTP.objects
        .select_for_update()
        .filter(
            user=user,
            purpose=purpose,
            used=False,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp:
        return False

    now = timezone.now()

    if otp.expires_at <= now:
        return False

    if otp.attempts >= OTP_MAX_ATTEMPTS:
        return False

    if not check_password(str(code).strip(), otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        return False

    otp.used = True
    otp.used_at = now
    otp.save(update_fields=["used", "used_at"])

    SecurityEvent.objects.create(
        user=user,
        event_type="OTP_VERIFIED",
        success=True,
        metadata={"purpose": purpose},
    )

    return True
