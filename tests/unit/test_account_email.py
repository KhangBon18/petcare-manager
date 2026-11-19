import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from cryptography.fernet import Fernet

from petcare.email_address import normalize_email
from petcare.services import mail_service


class EmailAddressTests(unittest.TestCase):
    def test_normalizes_ascii_and_internationalized_domains(self):
        self.assertEqual(normalize_email("  Person+tag@Exämple.org "), "person+tag@xn--exmple-cua.org")
        self.assertIsNone(normalize_email("not-an-address"))
        self.assertIsNone(normalize_email("name@example.com\r\nBcc:attacker@example.net"))
        self.assertIsNone(normalize_email("name..dots@example.com"))


class MailServiceTests(unittest.TestCase):
    def test_sends_text_email_over_starttls(self):
        app = Flask("mail-service-test")
        app.config.update(
            APP_ENV="test",
            MAIL_HOST="smtp.example.test",
            MAIL_PORT=587,
            MAIL_USERNAME="mailer",
            MAIL_PASSWORD="secret",
            MAIL_FROM="no-reply@example.test",
            MAIL_FROM_NAME="PetCare Manager",
            MAIL_STARTTLS=True,
            MAIL_TIMEOUT_SECONDS=7,
            MAIL_OUTBOX_KEY=Fernet.generate_key().decode("ascii"),
        )
        client = MagicMock()
        client.__enter__.return_value = client
        context = object()
        with (
            app.app_context(),
            patch("petcare.services.mail_service.smtplib.SMTP", return_value=client) as smtp,
            patch("petcare.services.mail_service.ssl.create_default_context", return_value=context),
        ):
            mail_service.send_text_email(
                "Person@Example.test", "Test subject", "One-time link: https://example.test/t?token=secret"
            )

        smtp.assert_called_once_with("smtp.example.test", 587, timeout=7)
        client.starttls.assert_called_once_with(context=context)
        client.login.assert_called_once_with("mailer", "secret")
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["To"], "person@example.test")
        self.assertIn("One-time link", message.get_content())

    def test_rejects_bad_headers_and_requires_tls_in_production(self):
        config = {
            "APP_ENV": "production",
            "MAIL_HOST": "smtp.example.test",
            "MAIL_PORT": 587,
            "MAIL_USERNAME": "",
            "MAIL_PASSWORD": "",
            "MAIL_FROM": "no-reply@example.test",
            "MAIL_FROM_NAME": "PetCare",
            "MAIL_STARTTLS": True,
            "MAIL_TIMEOUT_SECONDS": 10,
            "MAIL_OUTBOX_KEY": Fernet.generate_key().decode("ascii"),
        }
        missing_outbox_key = {**config, "MAIL_OUTBOX_KEY": ""}
        with self.assertRaisesRegex(RuntimeError, "MAIL_OUTBOX_KEY"):
            mail_service.validate_runtime_config(missing_outbox_key)
        mail_service.validate_production_config(config)
        config["MAIL_STARTTLS"] = False
        with self.assertRaisesRegex(RuntimeError, "STARTTLS"):
            mail_service.validate_production_config(config)

        app = Flask("mail-service-test")
        app.config.update(config, MAIL_STARTTLS=True)
        with app.app_context(), self.assertRaises(mail_service.MailDeliveryError):
            mail_service.send_text_email("person@example.test", "Injected\r\nBcc: x", "body")


if __name__ == "__main__":
    unittest.main()
