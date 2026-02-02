"""
Structured Logging with Trace Correlation
==========================================

This module configures structured logging that:
1. Outputs logs as JSON (machine-parseable)
2. Automatically includes trace_id and span_id (correlation)
3. Adds consistent fields to every log (service name, timestamp)
4. Supports both JSON (production) and text (development) formats

WHY STRUCTURED LOGGING?
-----------------------

Traditional logging:
    logger.info(f"User {email} logged in successfully")
    # Output: "2024-01-29 10:15:32 INFO User test@example.com logged in successfully"

    Problems:
    - How do you search for all logins by a specific user?
    - How do you count logins per hour?
    - How do you correlate this log with the request that caused it?

Structured logging:
    logger.info("User login successful", extra={"user_email": email})
    # Output: {"timestamp": "...", "message": "User login successful",
    #          "user_email": "test@example.com", "trace_id": "abc123..."}

    Benefits:
    - Query: WHERE user_email = 'test@example.com'
    - Aggregate: COUNT(*) GROUP BY hour
    - Correlate: Click trace_id to see full request journey

TRACE CORRELATION EXPLAINED:
---------------------------

Every HTTP request gets a unique trace_id. This ID:
- Is generated when the request arrives (or extracted from incoming headers)
- Is stored in a thread-local Context object
- Is accessible throughout the request lifecycle
- Is automatically added to all logs during that request

This means if you search for a trace_id in your logs, you'll find ALL logs
related to that single request, even if they were generated in different
functions, modules, or even services.

EXAMPLE OUTPUT:
--------------

JSON format (production):
{
    "timestamp": "2024-01-29T10:15:32.123456Z",
    "level": "INFO",
    "message": "User login successful",
    "logger": "app.services.auth",
    "service": "rag-admin-backend",
    "trace_id": "abc123def456789...",
    "span_id": "xyz789...",
    "user_email": "test@example.com"
}

Text format (development):
2024-01-29 10:15:32.123 | INFO | app.services.auth | [abc123de] User login successful | user_email=test@example.com
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Optional, Any

# python-json-logger provides a JSON formatter for Python's logging module
# It converts log records to JSON format with customizable fields
from pythonjsonlogger import jsonlogger

# OpenTelemetry trace module for accessing current span context
# This is how we get the trace_id and span_id for correlation
from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """
    A logging filter that injects trace context into every log record.

    HOW FILTERS WORK:
    ----------------
    In Python's logging system, filters can modify log records before they're
    formatted and output. We use this to add trace_id and span_id fields.

    The filter method is called for every log record. We:
    1. Get the current span from OpenTelemetry context
    2. Extract trace_id and span_id
    3. Add them as attributes on the log record
    4. The formatter then includes these in the output

    WHY A FILTER (not formatter)?
    ----------------------------
    Filters modify the LogRecord object, making fields available to ANY formatter.
    This means both JSON and text formatters can access trace_id without
    duplicating the extraction logic.

    CONTEXT PROPAGATION:
    -------------------
    OpenTelemetry uses Context to propagate trace information. When FastAPI
    receives a request, the instrumentor:
    1. Creates or extracts a span
    2. Attaches it to the current Context

    Our filter retrieves this span using trace.get_current_span().
    If there's no active span (e.g., during startup), we use placeholder values.
    """

    def __init__(self, service_name: str):
        """
        Initialize the filter with service name.

        Args:
            service_name: The service identifier (added to every log)
        """
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add trace context to the log record.

        This method is called for every log message. It:
        1. Gets the current OpenTelemetry span (if any)
        2. Extracts trace_id and span_id
        3. Adds them to the record as attributes

        Args:
            record: The log record to modify

        Returns:
            True (always allow the record through)
        """
        # Add service name to every log
        record.service = self.service_name

        # Get the current span from OpenTelemetry context
        # This returns INVALID_SPAN if there's no active span
        current_span = trace.get_current_span()

        # Get the span context (contains trace_id, span_id, flags)
        span_context = current_span.get_span_context()

        # Check if we have a valid span context
        # Invalid context means no active trace (e.g., during startup)
        if span_context.is_valid:
            # Format trace_id as 32-character hex string (standard format)
            # trace_id is a 128-bit integer, we convert to hex and pad
            record.trace_id = format(span_context.trace_id, '032x')

            # Format span_id as 16-character hex string
            # span_id is a 64-bit integer
            record.span_id = format(span_context.span_id, '016x')
        else:
            # No active trace - use placeholder values
            # This happens during application startup or background tasks
            record.trace_id = "00000000000000000000000000000000"
            record.span_id = "0000000000000000"

        # Always return True to allow the log record through
        # Returning False would suppress the log
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds standard fields to every log.

    WHAT A FORMATTER DOES:
    ---------------------
    A formatter converts a LogRecord object into a string. The default formatter
    produces text like "2024-01-29 10:15:32 INFO message". Our custom formatter
    produces JSON with additional fields.

    BASE CLASS (JsonFormatter):
    --------------------------
    python-json-logger's JsonFormatter handles:
    - Converting the record to a dictionary
    - Serializing to JSON
    - Handling non-JSON-serializable types

    OUR CUSTOMIZATIONS:
    ------------------
    - Add ISO-8601 timestamp with timezone (standard format)
    - Ensure 'level' is uppercase for consistency
    - Include logger name for tracing log source

    OUTPUT EXAMPLE:
    --------------
    {
        "timestamp": "2024-01-29T10:15:32.123456+00:00",
        "level": "INFO",
        "message": "User login successful",
        "logger": "app.services.auth_service",
        "service": "rag-admin-backend",
        "trace_id": "abc123...",
        "span_id": "def456...",
        "user_email": "test@example.com"  // from extra={}
    }
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any]
    ) -> None:
        """
        Add custom fields to the JSON log record.

        This method is called by JsonFormatter before serializing.
        We add/modify fields here to ensure consistent output.

        Args:
            log_record: The dictionary that will be serialized to JSON
            record: The original Python LogRecord object
            message_dict: Additional message data (from extra={})
        """
        # Call parent to get standard fields
        super().add_fields(log_record, record, message_dict)

        # Add ISO-8601 timestamp with timezone
        # This is the standard format for log timestamps
        # Example: "2024-01-29T10:15:32.123456+00:00"
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.now(timezone.utc).isoformat()

        # Add log level from the LogRecord object
        # The level is stored as levelname on the record (e.g., "INFO", "WARNING")
        # We normalize to uppercase for consistency across all logs
        log_record['level'] = record.levelname.upper()

        # Add logger name (helps identify which module produced the log)
        if not log_record.get('logger'):
            log_record['logger'] = record.name


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for local development.

    Produces output like:
    2024-01-29 10:15:32.123 | INFO | app.services.auth | [abc123de] User login | email=test@example.com

    WHY A SEPARATE FORMATTER?
    ------------------------
    JSON is great for production (machine parsing) but hard to read in a terminal.
    During development, you want logs you can quickly scan visually.

    This formatter:
    - Uses pipe separators for easy scanning
    - Shows only first 8 chars of trace_id (enough to correlate)
    - Displays extra fields as key=value pairs

    Switch between formats using LOG_FORMAT environment variable:
    - LOG_FORMAT=json → CustomJsonFormatter
    - LOG_FORMAT=text → DevelopmentFormatter
    """

    def __init__(self):
        # Format: timestamp | level | logger | [trace] message
        super().__init__(
            fmt='%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)s | [%(trace_short)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as human-readable text.

        Args:
            record: The log record to format

        Returns:
            Formatted string
        """
        # Add shortened trace_id for display (first 8 characters)
        # This is enough to correlate logs visually without cluttering
        if hasattr(record, 'trace_id') and record.trace_id:
            record.trace_short = record.trace_id[:8]
        else:
            record.trace_short = '--------'

        # Format the base message
        formatted = super().format(record)

        # Append any extra fields as key=value pairs
        # This preserves structured data in a readable format
        extras = []
        # Standard fields to skip (already in the format string or internal)
        skip_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'trace_id', 'span_id', 'trace_short', 'service', 'message',
            'taskName', 'asctime'  # asctime is already in the timestamp
        }

        for key, value in record.__dict__.items():
            if key not in skip_fields and not key.startswith('_'):
                extras.append(f'{key}={value}')

        if extras:
            formatted += ' | ' + ' '.join(extras)

        return formatted


def setup_logging(
    service_name: str,
    level: str = "INFO",
    log_format: str = "json",
) -> None:
    """
    Configure structured logging for the application.

    This function:
    1. Creates a root logger configuration
    2. Adds trace context injection (filter)
    3. Sets up appropriate formatter (JSON or text)
    4. Configures output to stdout (for Docker)

    WHY STDOUT?
    ----------
    Docker (and most container orchestrators) capture stdout/stderr.
    By logging to stdout:
    - Logs appear in `docker logs <container>`
    - Logs can be collected by log aggregators
    - No need to manage log files inside containers

    Args:
        service_name: Service identifier added to every log
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: "json" for production, "text" for development

    Example:
        >>> setup_logging(
        ...     service_name="rag-admin-backend",
        ...     level="INFO",
        ...     log_format="json"
        ... )
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started", extra={"version": "1.0.0"})
        # Output: {"timestamp": "...", "message": "Application started",
        #          "version": "1.0.0", "trace_id": "...", ...}
    """
    # Get the root logger - this affects all loggers in the application
    root_logger = logging.getLogger()

    # Convert string level to logging constant
    # "INFO" → logging.INFO (20)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicate logs
    # This is important when setup_logging is called multiple times (e.g., tests)
    root_logger.handlers.clear()

    # Create console handler (outputs to stdout)
    # StreamHandler defaults to stderr, but stdout is better for Docker
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    # Add trace context filter (injects trace_id, span_id, service)
    # This filter is applied to ALL handlers on the root logger
    trace_filter = TraceContextFilter(service_name)
    console_handler.addFilter(trace_filter)

    # Choose formatter based on configuration
    if log_format.lower() == "json":
        # JSON format for production
        # Include these fields in every log entry
        formatter = CustomJsonFormatter(
            # These are the fields from the LogRecord that we want in JSON
            # Additional fields (trace_id, span_id, service) come from the filter
            # Extra fields (passed via extra={}) are automatically included
            fmt='%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        # Human-readable format for development
        formatter = DevelopmentFormatter()

    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure specific loggers to reduce noise
    # These libraries are verbose at DEBUG level
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)

    # Log that logging is configured (using the new format!)
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": level,
            "log_format": log_format,
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the specified module.

    This is a convenience function that returns a logger with the module name.
    Use __name__ to get a logger named after the current module.

    BEST PRACTICE:
    -------------
    At the top of each module:

        from app.observability.logging import get_logger
        logger = get_logger(__name__)

    Then use:
        logger.info("Something happened", extra={"key": "value"})

    The logger name (e.g., "app.services.auth_service") helps identify
    which module produced the log.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
