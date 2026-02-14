"""
Backend logging configuration for debugging and process tracking.

Logs to both console and a temporary file (backend_debug.log in temp dir).
Captures: parameter types/values, processing counts, errors with full traceback.
"""

import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _get_log_file_path() -> Path:
    """Return path to temporary debug log file."""
    return Path(tempfile.gettempdir()) / "backend_debug.log"


def setup_logging(
    level: int = logging.DEBUG,
    log_to_file: bool = True,
    log_file_path: Optional[Path] = None,
) -> logging.Logger:
    """
    Configure backend logger with console and optional file output.

    Returns:
        Logger instance for backend modules to use.
    """
    logger = logging.getLogger("backend")
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(level)
    logger.propagate = False

    # Console handler - human-readable format
    console_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(console_fmt)
    logger.addHandler(ch)

    # File handler - more detailed for debugging
    if log_to_file:
        file_path = log_file_path or _get_log_file_path()
        try:
            fh = logging.FileHandler(file_path, encoding="utf-8", mode="a")
            fh.setLevel(level)
            file_fmt = logging.Formatter(
                "[%(asctime)s] %(levelname)s [%(name)s] %(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            fh.setFormatter(file_fmt)
            logger.addHandler(fh)
            logger.info(f"Debug log file: {file_path}")
        except OSError as e:
            logger.warning(f"Could not create log file {file_path}: {e}")

    return logger


def log_params(logger: logging.Logger, endpoint: str, params: Dict[str, Any]) -> None:
    """Log received parameters with types for debugging."""
    lines = [f"[{endpoint}] Received parameters:"]
    for k, v in params.items():
        t = type(v).__name__
        # Truncate long values (e.g. file content)
        if isinstance(v, (bytes, bytearray)):
            display = f"<bytes len={len(v)}>"
        elif isinstance(v, str) and len(v) > 200:
            display = repr(v[:200]) + "..."
        else:
            display = repr(v)
        lines.append(f"  {k}: ({t}) {display}")
    logger.debug("\n".join(lines))


def log_error(logger: logging.Logger, context: str, exc: BaseException) -> None:
    """Log error with type and full traceback."""
    import traceback

    err_type = type(exc).__name__
    logger.error(
        f"[{context}] Error type: {err_type}, message: {str(exc)}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )


# Initialize on import
_logger = setup_logging()


def get_logger(name: str = "backend") -> logging.Logger:
    """Get the backend logger. Use name='backend.pipeline.X' for sub-modules."""
    return logging.getLogger(name)
