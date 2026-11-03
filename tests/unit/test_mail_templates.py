import unittest

from petcare.services.mail_templates import (
    account_token_email,
    invitation_email,
    ownership_transfer_email,
)


class MailTemplateLocalizationTests(unittest.TestCase):
    def test_account_security_emails_match_expiry_and_locale(self):
        subject, body = account_token_email(
            "email_verification", "https://example.test/verify?token=secret", "en"
        )
        self.assertEqual(subject, "Verify your PetCare Manager email")
        self.assertIn("within 24 hours", body)
        self.assertIn("https://example.test/verify?token=secret", body)
        self.assertNotIn("Xác minh", body)

        subject, body = account_token_email("password_reset", "/reset", "vi")
        self.assertEqual(subject, "Đặt lại mật khẩu PetCare Manager")
        self.assertIn("30 phút", body)

    def test_invitation_is_one_time_and_has_the_seven_day_expiry(self):
        subject, body = invitation_email("Harbor Pets", "admin", "/invite", "en")
        self.assertEqual(subject, "Invitation to join a store on PetCare Manager")
        self.assertIn('join "Harbor Pets" as an administrator', body)
        self.assertIn("within 7 days", body)
        self.assertIn("/invite", body)

        _, staff_body = invitation_email("Harbor Pets", "staff", "/invite", "en")
        self.assertIn("as a staff member", staff_body)

    def test_ownership_notice_requires_in_app_reauthentication(self):
        subject, body = ownership_transfer_email(
            "Harbor Pets", "target", "/ownership", "en"
        )
        self.assertEqual(subject, "Store ownership transfer request")
        self.assertIn("within 72 hours", body)
        self.assertIn("current password", body)
        self.assertIn("cannot be used to approve", body)
