"""
Centralized logging with file + console output using Rich for pretty terminal logs.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that silently handles PermissionError on Windows.
    
    On Windows, log rotation fails with WinError 32 when another process
    (dashboard, test runner, etc.) holds the log file open. Instead of
    spamming stderr with hundreds of --- Logging error --- tracebacks,
    this handler catches the error and continues writing to the current file.
    """
    
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            # Another process has the file locked — skip rotation
            # The file will be rotated on the next opportunity
            pass


def setup_logger(
    name: str = "job_ai_system",
    level: str = "INFO",
    log_file: str = "logs/system.log",
    max_bytes: int = 5_242_880,
    backup_count: int = 3,
) -> logging.Logger:
    """Create and configure a logger with both console (Rich) and file handlers."""

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # --- Console handler (Rich) ---
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
    )
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # --- File handler (safe rotating) ---
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = SafeRotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger