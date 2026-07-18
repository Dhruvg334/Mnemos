from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from mnemos.core.config import settings

logger = logging.getLogger(__name__)


async def send_verification_email(*, recipient: str, verification_url: str) -> None:
    if settings.email_delivery_mode == "log":
        logger.info(
            "email.verification_link",
            extra={"recipient": recipient, "verification_url": verification_url},
        )
        return

    if settings.email_delivery_mode != "smtp":
        raise RuntimeError("Unsupported email delivery mode")

    message = EmailMessage()
    message["Subject"] = "Verify your Mnemos account"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Verify your Mnemos account by opening this link:\n\n"
        f"{verification_url}\n\n"
        "This link expires shortly and can only be used once."
    )

    def deliver() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)

    await asyncio.to_thread(deliver)
