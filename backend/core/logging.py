import logging
import logging.handlers
import os
from datetime import datetime
import json
from typing import Any, Dict

from backend.core.config import settings, get_log_level


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)


class StructuredLogger:
    """Structured logging helper"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log_event(self, event: str, level: str = "INFO", **kwargs):
        """Log structured event with context"""
        log_method = getattr(self.logger, level.lower())

        for key, value in kwargs.items():
            setattr(self.logger, key, value)

        log_method(event)

    def log_error(self, event: str, error: Exception, **kwargs):
        """Log error with context"""
        kwargs["error_type"] = type(error).__name__
        kwargs["error_message"] = str(error)
        self.log_event(event, "ERROR", **kwargs)

    def log_request(self, method: str, path: str, status_code: int, **kwargs):
        """Log HTTP request"""
        self.log_event(
            f"{method} {path} - {status_code}",
            "INFO",
            request_method=method,
            request_path=path,
            status_code=status_code,
            **kwargs,
        )

    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metric"""
        self.log_event(
            f"{operation} took {duration:.3f}s",
            "DEBUG",
            operation=operation,
            duration_ms=duration * 1000,
            **kwargs,
        )


def setup_logging():
    """Configure logging system"""

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(get_log_level())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(get_log_level())
    console_formatter = logging.Formatter(settings.LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (rotating)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE, maxBytes=10485760, backupCount=10  # 10MB
        )
        file_handler.setLevel(get_log_level())

        # Use JSON formatter for file logs
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        root_logger.error(f"Failed to setup file logging: {str(e)}")

    # Set specific loggers
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    root_logger.info(f"Logging configured. Level: {get_log_level()}, File: {settings.LOG_FILE}")


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)


# Middleware for request logging
class RequestLoggingMiddleware:
    """Middleware to log all requests"""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger("request_logging")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time
        from datetime import datetime

        # Capture request info
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        # Capture status code from response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                self.logger.log_request(method, path, status_code)

            await send(message)

        # Call app and measure time
        start_time = time.time()
        await self.app(scope, receive, send_wrapper)
        duration = time.time() - start_time

        if duration > 1.0:  # Log slow requests
            self.logger.log_performance(f"{method} {path}", duration)


# Performance monitoring
class PerformanceMonitor:
    """Monitor and log performance metrics"""

    def __init__(self):
        self.logger = get_logger("performance")
        self.metrics = {}

    def record_operation(
        self, operation: str, duration: float, status: str = "success", **metadata
    ):
        """Record operation performance"""
        if operation not in self.metrics:
            self.metrics[operation] = []

        self.metrics[operation].append(
            {
                "duration": duration,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                **metadata,
            }
        )

        if duration > 1.0:
            self.logger.log_performance(operation, duration, status=status, **metadata)

    def get_average_duration(self, operation: str) -> float:
        """Get average duration for operation"""
        if operation not in self.metrics:
            return 0.0

        durations = [m["duration"] for m in self.metrics[operation]]
        return sum(durations) / len(durations) if durations else 0.0

    def get_stats(self, operation: str = None) -> Dict[str, Any]:
        """Get performance statistics"""
        if operation:
            if operation not in self.metrics:
                return {}

            ops = self.metrics[operation]
            durations = [m["duration"] for m in ops]
            return {
                "operation": operation,
                "count": len(ops),
                "average_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
            }

        # Return stats for all operations
        stats = {}
        for op in self.metrics:
            stats[op] = self.get_stats(op)

        return stats


# Global performance monitor
performance_monitor = PerformanceMonitor()


def monitor_operation(operation: str):
    """Decorator to monitor operation performance"""
    import functools
    import time

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                performance_monitor.record_operation(operation, duration, "success")
                return result
            except Exception as e:
                duration = time.time() - start
                performance_monitor.record_operation(operation, duration, "error", error=str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                performance_monitor.record_operation(operation, duration, "success")
                return result
            except Exception as e:
                duration = time.time() - start
                performance_monitor.record_operation(operation, duration, "error", error=str(e))
                raise

        # Return appropriate wrapper
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
