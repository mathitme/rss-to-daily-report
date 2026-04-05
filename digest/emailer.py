import smtplib
from email.message import EmailMessage
from pathlib import Path

from digest.runtime import EmailSettings


class EmailSendError(RuntimeError):
    pass


def send_report_email(subject: str, attachment_path: str | Path, settings: EmailSettings) -> None:
    if not settings.enabled:
        return

    attachment = Path(attachment_path)
    if not attachment.exists():
        raise EmailSendError(f"Attachment not found: {attachment}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.from_address
    message["To"] = settings.to_address
    message.set_content(f"Attached report: {attachment.name}")

    with attachment.open("rb") as f:
        data = f.read()
    message.add_attachment(
        data,
        maintype="text",
        subtype="markdown",
        filename=attachment.name,
    )

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
