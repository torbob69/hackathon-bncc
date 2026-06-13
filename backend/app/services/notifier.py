"""
Outbound notification delivery.

Functions:
  send_activation_email    — sends activation link via Gmail SMTP
  send_activation_whatsapp — sends activation link via Fonnte WhatsApp API
  dispatch_activation      — picks the right channel(s) and fires them
"""

import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email_sync(to_email: str, activation_url: str, name: str) -> None:
    """Blocking SMTP send — meant to be called via asyncio.to_thread."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Aktivasi Akun KoperaLink Anda"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"] = to_email

    html_body = f"""\
<html>
  <body style="font-family: sans-serif; color: #333;">
    <p>Halo <strong>{name}</strong>,</p>
    <p>Terima kasih telah mendaftar di <strong>KoperaLink</strong>.</p>
    <p>Klik tautan di bawah ini untuk mengaktifkan akun Anda:</p>
    <p>
      <a href="{activation_url}" style="
        display: inline-block;
        padding: 10px 20px;
        background-color: #16a34a;
        color: #fff;
        text-decoration: none;
        border-radius: 4px;
      ">Aktifkan Akun</a>
    </p>
    <p>Atau salin tautan berikut ke browser Anda:</p>
    <p><a href="{activation_url}">{activation_url}</a></p>
    <p>Tautan ini berlaku selama <strong>48 jam</strong>.</p>
    <p>Salam,<br/>Tim KoperaLink</p>
  </body>
</html>
"""
    plain_body = (
        f"Halo {name},\n\n"
        "Terima kasih telah mendaftar di KoperaLink.\n\n"
        "Klik tautan berikut untuk mengaktifkan akun Anda:\n"
        f"{activation_url}\n\n"
        "Tautan ini berlaku selama 48 jam.\n\n"
        "Salam,\nTim KoperaLink"
    )

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, to_email, msg.as_string())


async def _send_email_raising(to_email: str, activation_url: str, name: str) -> None:
    """Like send_activation_email but raises on failure — used by the test endpoint."""
    await asyncio.to_thread(_send_email_sync, to_email, activation_url, name)


async def send_activation_email(to_email: str, activation_url: str, name: str) -> None:
    """Send an account activation link via Gmail SMTP."""
    if not settings.SMTP_USER:
        logger.warning(
            "SMTP_USER is not configured — skipping activation email to %s", to_email
        )
        return

    try:
        await asyncio.to_thread(_send_email_sync, to_email, activation_url, name)
        logger.info("Activation email sent to %s", to_email)
    except Exception:
        logger.warning(
            "Failed to send activation email to %s", to_email, exc_info=True
        )


async def send_activation_whatsapp(
    to_phone: str, activation_url: str, name: str
) -> None:
    """Send an account activation link via Fonnte WhatsApp API."""
    if not settings.FONNTE_TOKEN:
        logger.warning(
            "FONNTE_TOKEN is not configured — skipping activation WhatsApp to %s",
            to_phone,
        )
        return

    message = (
        f"Halo {name}, selamat datang di KoperaLink!\n"
        "Klik link berikut untuk mengaktifkan akun Anda:\n"
        f"{activation_url}\n"
        "Link berlaku 48 jam."
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.fonnte.com/send",
                headers={"Authorization": settings.FONNTE_TOKEN},
                data={
                    "target": to_phone,
                    "message": message,
                    "countryCode": "62",
                },
            )
        if response.is_success:
            logger.info(
                "Activation WhatsApp sent to %s (status %s)",
                to_phone,
                response.status_code,
            )
        else:
            logger.warning(
                "Fonnte returned non-2xx status %s for %s: %s",
                response.status_code,
                to_phone,
                response.text,
            )
    except Exception:
        logger.warning(
            "Failed to send activation WhatsApp to %s", to_phone, exc_info=True
        )


async def dispatch_activation(
    *,
    email: str | None,
    phone: str | None,
    activation_url: str,
    name: str,
) -> None:
    """
    Dispatch activation notifications via all available channels.

    Sends email and/or WhatsApp concurrently when both are provided.
    Best-effort — individual channel failures are logged but never raised.
    """
    tasks = []

    if email is not None:
        tasks.append(send_activation_email(email, activation_url, name))

    if phone is not None:
        tasks.append(send_activation_whatsapp(phone, activation_url, name))

    if not tasks:
        logger.warning(
            "No contact method available for activation dispatch (name=%s)", name
        )
        return

    await asyncio.gather(*tasks)
