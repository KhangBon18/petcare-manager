"""Small SMTP adapter with mandatory TLS in production."""

from email.message import EmailMessage
from email.utils import formataddr
import json
import smtplib
import ssl

from cryptography.fernet import Fernet
from flask import current_app
import mysql.connector

from petcare.database.connection import transaction
from petcare.email_address import normalize_email
from petcare.repositories import mail_outbox_repo


class MailDeliveryError(Exception):
    """A configured mail server could not accept a message."""


def is_configured(config=None):
    config = config or current_app.config
    return bool(config.get("MAIL_HOST") and config.get("MAIL_FROM"))


def validate_runtime_config(config):
    port = int(config.get("MAIL_PORT", 587))
    timeout = int(config.get("MAIL_TIMEOUT_SECONDS", 10))
    from_name = config.get("MAIL_FROM_NAME", "PetCare Manager")
    host = config.get("MAIL_HOST", "")
    if not 1 <= port <= 65535:
        raise RuntimeError("MAIL_PORT must be between 1 and 65535.")
    if not 3 <= timeout <= 60:
        raise RuntimeError("MAIL_TIMEOUT_SECONDS must be between 3 and 60 seconds.")
    if any(char in str(host) for char in "\r\n"):
        raise RuntimeError("MAIL_HOST is invalid.")
    if len(str(from_name)) > 120 or any(char in str(from_name) for char in "\r\n"):
        raise RuntimeError("MAIL_FROM_NAME is invalid.")
    if bool(config.get("MAIL_USERNAME")) != bool(config.get("MAIL_PASSWORD")):
        raise RuntimeError("MAIL_USERNAME and MAIL_PASSWORD must be configured together.")
    outbox_key = config.get("MAIL_OUTBOX_KEY", "")
    if is_configured(config) and not outbox_key:
        raise RuntimeError("MAIL_OUTBOX_KEY is required when SMTP email delivery is configured.")
    if outbox_key:
        try:
            Fernet(outbox_key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as exc:
            raise RuntimeError("MAIL_OUTBOX_KEY must be a valid Fernet key.") from exc


def validate_production_config(config):
    validate_runtime_config(config)
    if not is_configured(config):
        raise RuntimeError("Production requires MAIL_HOST and MAIL_FROM for account verification and recovery.")
    if not config.get("MAIL_STARTTLS"):
        raise RuntimeError("Production email delivery requires SMTP STARTTLS.")
    if not normalize_email(config.get("MAIL_FROM")):
        raise RuntimeError("MAIL_FROM must be a valid email address.")


def _validated_payload(recipient, subject, body):
    config = current_app.config
    recipient = normalize_email(recipient)
    sender = normalize_email(config.get("MAIL_FROM"))
    if not is_configured(config) or not recipient or not sender:
        raise MailDeliveryError("Email delivery is not configured.")
    from_name = str(config.get("MAIL_FROM_NAME", "PetCare Manager"))
    if any(char in from_name for char in "\r\n") or len(from_name) > 120:
        raise MailDeliveryError("Email sender name is invalid.")
    if not isinstance(subject, str) or "\r" in subject or "\n" in subject:
        raise MailDeliveryError("Email subject is invalid.")
    if not isinstance(body, str) or len(body) > 20_000:
        raise MailDeliveryError("Email body is invalid.")
    return {"recipient": recipient, "subject": subject, "body": body}


def enqueue_text_email(recipient, subject, body, expires_at=None, connection=None):
    payload = _validated_payload(recipient, subject, body)
    key = current_app.config.get("MAIL_OUTBOX_KEY", "")
    if not key:
        raise MailDeliveryError("Email outbox encryption is not configured.")
    encrypted = Fernet(key.encode("ascii")).encrypt(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    try:
        if connection is not None:
            return mail_outbox_repo.enqueue(connection, encrypted, expires_at=expires_at)
        with transaction() as db_connection:
            return mail_outbox_repo.enqueue(db_connection, encrypted, expires_at=expires_at)
    except mysql.connector.Error as exc:
        raise MailDeliveryError("The email message could not be queued.") from exc


def send_text_email(recipient, subject, body):
    payload = _validated_payload(recipient, subject, body)
    recipient, subject, body = payload["recipient"], payload["subject"], payload["body"]
    config = current_app.config
    sender = normalize_email(config.get("MAIL_FROM"))
    from_name = str(config.get("MAIL_FROM_NAME", "PetCare Manager"))

    message = EmailMessage()
    message["From"] = formataddr((from_name, sender))
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(
            config["MAIL_HOST"],
            int(config.get("MAIL_PORT", 587)),
            timeout=int(config.get("MAIL_TIMEOUT_SECONDS", 10)),
        ) as client:
            client.ehlo()
            if config.get("MAIL_STARTTLS", True):
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            elif config.get("APP_ENV") == "production":
                raise MailDeliveryError("SMTP TLS is required in production.")
            username = config.get("MAIL_USERNAME", "")
            if username:
                client.login(username, config.get("MAIL_PASSWORD", ""))
            client.send_message(message)
    except MailDeliveryError:
        raise
    except Exception as exc:
        raise MailDeliveryError("The configured mail server did not accept the message.") from exc
