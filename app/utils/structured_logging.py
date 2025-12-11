"""Structured JSON logging configuration."""

import logging
import json
import sys
from datetime import datetime
from flask import has_request_context, request, g
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with request context."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = datetime.utcnow().isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Add request context if available
        if has_request_context():
            log_record["request_id"] = getattr(g, "request_id", None)
            log_record["user_id"] = getattr(g, "user_id", None)
            log_record["ip_address"] = request.remote_addr
            log_record["method"] = request.method
            log_record["path"] = request.path
            log_record["user_agent"] = request.headers.get("User-Agent")

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_json_logging(app):
    """Configure JSON logging for production."""
    # Create JSON formatter
    formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")

    # Setup handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, app.config.get("LOG_LEVEL", "INFO")))
    root_logger.addHandler(handler)

    # Configure app logger
    app.logger.setLevel(getattr(logging, app.config.get("LOG_LEVEL", "INFO")))
    app.logger.addHandler(handler)

    return app


class StructuredLogger:
    """Structured logging helper."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, message: str, **kwargs):
        """Log info with structured data."""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning with structured data."""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs):
        """Log error with structured data."""
        self.logger.error(message, extra=kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug with structured data."""
        self.logger.debug(message, extra=kwargs)


# Example usage:
# logger = StructuredLogger(__name__)
# logger.info("Bug submitted", bug_id="123", product="Mobile App", is_duplicate=False)
