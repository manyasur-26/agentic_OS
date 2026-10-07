"""
Shared pytest fixtures and cleanup for Agentic OS tests.
"""

import logging
import sys
import pytest


@pytest.fixture(autouse=True)
def _close_log_handlers():
    """Close all log handlers after each test (Windows file-lock fix)."""
    yield
    # Close stdlib logging handlers
    for name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(name)
        logger.setLevel(logging.NOTSET)  # Reset level
        logger.propagate = True  # Reset propagation
        logger.disabled = False  # Enable logger
        for handler in list(logger.handlers):
            try:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            except Exception:
                pass
    
    # Close root logger handlers
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.handlers.clear()
    
    # Force flush and close std streams
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    
    # Close structlog processors
    try:
        import structlog
        structlog.reset_defaults()
    except Exception:
        pass
