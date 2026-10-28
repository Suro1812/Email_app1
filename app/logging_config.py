import logging
import os
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path


_STANDARD_LOG_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__)


class ExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_KEYS
            and not key.startswith("_")
        }
        if not extra:
            return message
        try:
            details = json.dumps(extra, sort_keys=True, default=str)
        except TypeError:
            details = str(extra)
        return f"{message} {details}"


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_email_reminders_file_logging", False):
        return

    log_dir = Path(os.getenv("EMAIL_REMINDERS_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = os.getenv("EMAIL_REMINDERS_LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    formatter = ExtraFormatter(
        "%(asctime)s %(levelname)s [%(processName)s] %(name)s: %(message)s"
    )

    app_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    logging.captureWarnings(True)
    root_logger._email_reminders_file_logging = True
