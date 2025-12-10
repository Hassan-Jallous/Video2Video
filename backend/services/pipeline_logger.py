"""
Pipeline Logger - Ultra-detailed logging for Video2Video debugging

Provides:
- Session-scoped logging with timestamps
- Structured JSON logs for easy parsing
- Redis storage for persistent logs
- Console output with color coding
- Automatic context tracking (function, file, line)
"""
import json
import time
import traceback
import functools
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from pathlib import Path

import redis

from config import settings


class PipelineLogger:
    """
    Ultra-detailed logger that tracks every step of the pipeline.

    Logs are stored in Redis under key: pipeline_logs:{session_id}
    Each log entry includes timestamp, level, context, and data.
    """

    # Log levels with colors for console
    LEVELS = {
        "DEBUG": "\033[90m",    # Gray
        "INFO": "\033[94m",     # Blue
        "SUCCESS": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",    # Red
        "CRITICAL": "\033[95m", # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or "global"
        self.redis_client = redis.from_url(settings.redis_url)
        self.start_time = time.time()
        self._step_counter = 0

    def set_session(self, session_id: str):
        """Set session ID for all subsequent logs"""
        self.session_id = session_id
        self.start_time = time.time()
        self._step_counter = 0
        self.info("SESSION_START", f"New logging session started: {session_id}")

    def _get_caller_info(self) -> Dict[str, Any]:
        """Get caller file, function, and line number"""
        stack = traceback.extract_stack()
        # Go back through stack to find the actual caller (not this file)
        for frame in reversed(stack[:-2]):
            if 'pipeline_logger' not in frame.filename:
                return {
                    "file": Path(frame.filename).name,
                    "function": frame.name,
                    "line": frame.lineno
                }
        return {"file": "unknown", "function": "unknown", "line": 0}

    def _log(
        self,
        level: str,
        category: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ):
        """Core logging method"""
        self._step_counter += 1
        elapsed = time.time() - self.start_time
        caller = self._get_caller_info()

        log_entry = {
            "step": self._step_counter,
            "timestamp": datetime.utcnow().isoformat(),
            "elapsed_sec": round(elapsed, 3),
            "level": level,
            "category": category,
            "message": message,
            "caller": caller,
            "session_id": self.session_id,
        }

        if data:
            # Sanitize sensitive data
            sanitized = self._sanitize_data(data)
            log_entry["data"] = sanitized

        if error:
            log_entry["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc()
            }

        # Store in Redis
        redis_key = f"pipeline_logs:{self.session_id}"
        self.redis_client.rpush(redis_key, json.dumps(log_entry))
        self.redis_client.expire(redis_key, 86400 * 7)  # Keep logs for 7 days

        # Console output with color
        color = self.LEVELS.get(level, "")
        location = f"{caller['file']}:{caller['line']}"

        # Format data preview (truncated)
        data_preview = ""
        if data:
            data_str = json.dumps(data, default=str)
            if len(data_str) > 200:
                data_preview = f" | data={data_str[:200]}..."
            else:
                data_preview = f" | data={data_str}"

        error_preview = ""
        if error:
            error_preview = f" | ERROR: {type(error).__name__}: {str(error)[:100]}"

        print(
            f"{color}[{level:8}]{self.RESET} "
            f"[{elapsed:7.2f}s] "
            f"[{location:30}] "
            f"[{category:20}] "
            f"{message}"
            f"{data_preview}"
            f"{error_preview}"
        )

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data like API keys and base64 images"""
        sanitized = {}
        for key, value in data.items():
            if any(k in key.lower() for k in ['key', 'token', 'password', 'secret']):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate long strings (like base64 images)
                sanitized[key] = f"{value[:100]}... [TRUNCATED, len={len(value)}]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list) and len(value) > 10:
                sanitized[key] = f"[LIST with {len(value)} items]"
            else:
                sanitized[key] = value
        return sanitized

    # Convenience methods for different log levels
    def debug(self, category: str, message: str, data: Optional[Dict] = None):
        self._log("DEBUG", category, message, data)

    def info(self, category: str, message: str, data: Optional[Dict] = None):
        self._log("INFO", category, message, data)

    def success(self, category: str, message: str, data: Optional[Dict] = None):
        self._log("SUCCESS", category, message, data)

    def warning(self, category: str, message: str, data: Optional[Dict] = None):
        self._log("WARNING", category, message, data)

    def error(self, category: str, message: str, error: Optional[Exception] = None, data: Optional[Dict] = None):
        self._log("ERROR", category, message, data, error)

    def critical(self, category: str, message: str, error: Optional[Exception] = None, data: Optional[Dict] = None):
        self._log("CRITICAL", category, message, data, error)

    # Specialized logging methods
    def api_request(self, service: str, endpoint: str, payload: Dict):
        """Log an outgoing API request"""
        self.info("API_REQUEST", f"{service} -> {endpoint}", {
            "endpoint": endpoint,
            "payload_keys": list(payload.keys()),
            "payload": payload
        })

    def api_response(self, service: str, status_code: int, response_data: Any, duration_ms: float):
        """Log an API response"""
        level = "SUCCESS" if 200 <= status_code < 300 else "ERROR"
        self._log(level, "API_RESPONSE", f"{service} <- {status_code} ({duration_ms:.0f}ms)", {
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response": response_data
        })

    def file_operation(self, operation: str, path: str, success: bool, details: Optional[Dict] = None):
        """Log file operations (read, write, extract, etc.)"""
        level = "SUCCESS" if success else "ERROR"
        data = {"path": path, "success": success}
        if details:
            data.update(details)
        self._log(level, "FILE_OP", f"{operation}: {path}", data)

    def pipeline_step(self, step_name: str, status: str, details: Optional[Dict] = None):
        """Log a major pipeline step"""
        level = "SUCCESS" if status == "completed" else ("ERROR" if status == "failed" else "INFO")
        self._log(level, "PIPELINE", f"{step_name} -> {status}", details)

    def get_logs(self, limit: int = 100) -> list:
        """Retrieve logs for current session"""
        redis_key = f"pipeline_logs:{self.session_id}"
        logs = self.redis_client.lrange(redis_key, -limit, -1)
        return [json.loads(log) for log in logs]

    def get_errors(self) -> list:
        """Get only error logs for current session"""
        all_logs = self.get_logs(limit=1000)
        return [log for log in all_logs if log.get("level") in ("ERROR", "CRITICAL")]

    def get_summary(self) -> Dict:
        """Get a summary of the session logs"""
        all_logs = self.get_logs(limit=1000)
        return {
            "session_id": self.session_id,
            "total_logs": len(all_logs),
            "errors": len([l for l in all_logs if l.get("level") == "ERROR"]),
            "warnings": len([l for l in all_logs if l.get("level") == "WARNING"]),
            "duration_sec": all_logs[-1]["elapsed_sec"] if all_logs else 0,
            "last_category": all_logs[-1]["category"] if all_logs else None,
            "last_message": all_logs[-1]["message"] if all_logs else None,
        }


def log_function(category: str = "FUNCTION"):
    """
    Decorator to automatically log function entry, exit, and errors.

    Usage:
        @log_function("VIDEO_GEN")
        async def generate_video(...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get logger from kwargs or create new one
            logger = kwargs.get('_logger') or PipelineLogger()

            # Log function entry
            logger.debug(category, f"ENTER: {func.__name__}", {
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            })

            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.success(category, f"EXIT: {func.__name__} ({duration:.0f}ms)")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(category, f"FAILED: {func.__name__} ({duration:.0f}ms)", error=e)
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = kwargs.get('_logger') or PipelineLogger()

            logger.debug(category, f"ENTER: {func.__name__}", {
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            })

            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.success(category, f"EXIT: {func.__name__} ({duration:.0f}ms)")
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(category, f"FAILED: {func.__name__} ({duration:.0f}ms)", error=e)
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global logger instance for quick access
pipeline_logger = PipelineLogger()
