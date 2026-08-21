from __future__ import annotations

import logging

from app.config.settings import Settings


class SecretRedactionFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self.secrets = [secret for secret in secrets if secret]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        record.msg = message
        record.args = ()
        return True


def configure_secret_redaction(settings: Settings) -> None:
    secrets = [
        settings.eth_private_key.get_secret_value(),
        settings.bnb_private_key.get_secret_value(),
        settings.sol_private_key.get_secret_value(),
        settings.user_bot_token.get_secret_value(),
        settings.admin_bot_token.get_secret_value(),
    ]
    redaction_filter = SecretRedactionFilter(secrets)
    root_logger = logging.getLogger()
    root_logger.addFilter(redaction_filter)
    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)

