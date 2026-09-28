"""
Email service abstraction for DataPilot.
Handles human-in-the-loop notifications (e.g. CAPTCHA challenges).
Supports swappable providers: SMTPEmailProvider and InMemoryEmailProvider.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings
from app.core.logger import logger


class EmailMessage:
    """Represents a formatted email message."""
    def __init__(self, to_email: str, subject: str, body: str, from_email: Optional[str] = None):
        self.to_email = to_email
        self.subject = subject
        self.body = body
        self.from_email = from_email or settings.SMTP_FROM_EMAIL
        self.sent_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "to_email": self.to_email,
            "from_email": self.from_email,
            "subject": self.subject,
            "body": self.body,
            "sent_at": self.sent_at.isoformat(),
        }


class EmailProvider(ABC):
    """Abstract email provider interface."""
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> bool:
        """Sends an email message. Returns True if delivery succeeded."""
        pass


class InMemoryEmailProvider(EmailProvider):
    """
    In-memory email provider used for testing and when SMTP is unconfigured.
    Captures sent messages in memory for test assertions and logs to logger.
    """
    def __init__(self):
        self.outbox: List[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> bool:
        self.outbox.append(message)
        logger.info(
            f"[InMemoryEmail] Email dispatched to {message.to_email} | Subject: '{message.subject}'"
        )
        return True

    def clear(self):
        self.outbox.clear()


class SMTPEmailProvider(EmailProvider):
    """
    Standard SMTP email provider with TLS support.
    """
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.host = host or settings.SMTP_HOST
        self.port = port or settings.SMTP_PORT
        self.username = username or settings.SMTP_USERNAME
        self.password = password or settings.SMTP_PASSWORD
        self.use_tls = use_tls if use_tls is not None else settings.SMTP_USE_TLS

    async def send_email(self, message: EmailMessage) -> bool:
        if not self.host:
            logger.warning("SMTP_HOST not configured. Email cannot be delivered via SMTP.")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = message.from_email
            msg["To"] = message.to_email
            msg["Subject"] = message.subject
            msg.attach(MIMEText(message.body, "plain"))

            # Send synchronously via standard library inside async-safe executor
            server = smtplib.SMTP(self.host, self.port, timeout=10)
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.sendmail(message.from_email, [message.to_email], msg.as_string())
            server.quit()
            logger.info(f"[SMTPEmail] Sent email to {message.to_email} via {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"[SMTPEmail] Failed to send email to {message.to_email}: {e}")
            return False


class EmailService:
    """
    Singleton email manager that routes emails to the active provider.
    """
    _instance: Optional["EmailService"] = None

    def __init__(self, provider: Optional[EmailProvider] = None):
        if provider:
            self._provider = provider
        elif settings.SMTP_HOST:
            self._provider = SMTPEmailProvider()
        else:
            self._provider = InMemoryEmailProvider()

    @property
    def provider(self) -> EmailProvider:
        return self._provider

    def set_provider(self, provider: EmailProvider):
        """Allows swapping email provider (e.g. for testing)."""
        self._provider = provider

    async def send_human_action_required_email(
        self,
        to_email: Optional[str],
        source_name: str,
        source_url: str,
        task_id: str,
    ) -> bool:
        """
        Sends an email alerting the client that a CAPTCHA/human verification challenge was encountered.
        Never includes secrets, API keys, cookies, or session tokens.
        """
        recipient = to_email or settings.DATAPILOT_AUTH_EMAIL
        if not recipient:
            logger.warning(
                f"No DATAPILOT_AUTH_EMAIL configured. Human action email for task '{task_id}' could not be addressed."
            )
            recipient = "client@datapilot.local"

        subject = "DataPilot needs your help to continue a collection task"

        # Explicit body format conforming to specifications
        body = (
            "DataPilot was collecting data from:\n\n"
            f"{source_name}\n"
            f"{source_url}\n\n"
            "The source requires a CAPTCHA/human verification before collection can continue.\n\n"
            "Please open the source URL and complete the CAPTCHA manually.\n\n"
            "Once completed, DataPilot can continue the collection workflow.\n\n"
            f"Task ID: {task_id}\n"
        )

        message = EmailMessage(
            to_email=recipient,
            subject=subject,
            body=body,
        )
        return await self._provider.send_email(message)


# Global singleton email service
email_service = EmailService()
