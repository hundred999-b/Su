from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import RecoveryCode, SecurityOTP
from .services import (
    consume_recovery_code,
    create_otp,
    generate_recovery_codes,
    get_security_profile,
    set_pin,
    verify_otp,
    verify_pin,
)


User = get_user_model()


class SecurityServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="security_test_user",
            password="test-password",
        )

    def test_pin_can_be_set_and_verified(self):
        set_pin(self.user, "123456")

        self.assertTrue(
            verify_pin(self.user, "123456")
        )

        self.assertFalse(
            verify_pin(self.user, "654321")
        )

    def test_pin_is_not_stored_plaintext(self):
        set_pin(self.user, "123456")

        profile = get_security_profile(self.user)

        self.assertNotEqual(
            profile.pin_hash,
            "123456",
        )

    def test_pin_rejects_short_pin(self):
        with self.assertRaises(ValueError):
            set_pin(self.user, "12345")

    def test_recovery_codes_are_one_time(self):
        codes = generate_recovery_codes(self.user, 20)

        self.assertEqual(len(codes), 20)

        self.assertTrue(
            consume_recovery_code(self.user, codes[0])
        )

        self.assertFalse(
            consume_recovery_code(self.user, codes[0])
        )

    def test_recovery_codes_are_not_stored_plaintext(self):
        codes = generate_recovery_codes(self.user, 20)

        stored = RecoveryCode.objects.filter(
            user=self.user
        ).first()

        self.assertNotEqual(
            stored.code_hash,
            codes[0],
        )

    def test_otp_can_be_verified_once(self):
        otp, code = create_otp(
            self.user,
            SecurityOTP.PURPOSE_PURCHASE,
        )

        self.assertTrue(
            verify_otp(
                self.user,
                SecurityOTP.PURPOSE_PURCHASE,
                code,
            )
        )

        self.assertFalse(
            verify_otp(
                self.user,
                SecurityOTP.PURPOSE_PURCHASE,
                code,
            )
        )

    def test_wrong_otp_is_rejected(self):
        create_otp(
            self.user,
            SecurityOTP.PURPOSE_WITHDRAWAL,
        )

        self.assertFalse(
            verify_otp(
                self.user,
                SecurityOTP.PURPOSE_WITHDRAWAL,
                "000000",
            )
        )
