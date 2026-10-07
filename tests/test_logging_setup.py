"""
Unit tests for Logging Setup.
"""

import pytest
import tempfile
import json
import logging
from pathlib import Path
from datetime import datetime

from core.logging_setup import (
    setup_logging,
    get_logger,
    AuditLogger,
    TraceLogger,
    get_audit_logger,
    get_trace_logger,
    reset_loggers
)
from core.config import LoggingConfig, Config, reset_config


@pytest.fixture
def temp_log_dir():
    """Create a temporary log directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def logging_config(temp_log_dir):
    """Create a logging config for testing."""
    return LoggingConfig(
        level="DEBUG",
        format="text",
        log_dir=temp_log_dir,
        max_file_size=1024,
        backup_count=2
    )


def test_setup_logging_json(logging_config):
    """Test setting up JSON logging."""
    logging_config.format = "json"
    setup_logging(logging_config)
    
    logger = get_logger("test")
    logger.info("test message", extra_data="test")
    
    # Check log file was created
    log_file = Path(logging_config.log_dir) / "agentic-os.log"
    assert log_file.exists()
    
    # Explicitly close file handler
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.close()
            root.removeHandler(handler)


def test_setup_logging_text(logging_config):
    """Test setting up text logging."""
    logging_config.format = "text"
    setup_logging(logging_config)
    
    logger = get_logger("test")
    logger.info("test message")
    
    # Check log file was created
    log_file = Path(logging_config.log_dir) / "agentic-os.log"
    assert log_file.exists()
    
    # Explicitly close file handler
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.close()
            root.removeHandler(handler)


def test_get_logger(logging_config):
    """Test getting a logger with component context."""
    setup_logging(logging_config)
    
    logger = get_logger("test_component")
    logger.info("test message")
    
    # Should not raise
    assert logger is not None
    
    # Explicitly close file handler
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.close()
            root.removeHandler(handler)


def test_audit_logger(temp_log_dir):
    """Test audit logger functionality."""
    audit_logger = AuditLogger(temp_log_dir)
    
    audit_logger.log(
        event_type="policy_check",
        actor="cli",
        action="submit_task",
        target="task-123",
        result="success",
        details={"intent": "test"}
    )
    
    # Check audit file was created
    audit_file = Path(temp_log_dir) / "audit.log"
    assert audit_file.exists()
    
    # Verify content
    with open(audit_file, 'r') as f:
        content = f.read()
    
    assert "policy_check" in content
    assert "cli" in content
    assert "submit_task" in content
    assert "success" in content
    
    audit_logger.close()


def test_audit_logger_multiple_events(temp_log_dir):
    """Test audit logger with multiple events."""
    audit_logger = AuditLogger(temp_log_dir)
    
    for i in range(5):
        audit_logger.log(
            event_type="test_event",
            actor="test",
            action=f"action_{i}",
            result="success"
        )
    
    audit_logger.close()
    
    audit_file = Path(temp_log_dir) / "audit.log"
    with open(audit_file, 'r') as f:
        lines = f.readlines()
    
    assert len(lines) == 5


def test_trace_logger(temp_log_dir):
    """Test trace logger functionality."""
    trace_logger = TraceLogger(temp_log_dir)
    
    trace_logger.log_trace({
        "event": "test_event",
        "task_id": "task-123",
        "data": "test"
    })
    
    # Check trace file was created
    trace_file = trace_logger._get_trace_file()
    assert trace_file.exists()
    
    # Verify content
    with open(trace_file, 'r') as f:
        lines = f.readlines()
    
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "test_event"
    assert data["task_id"] == "task-123"
    assert "timestamp" in data


def test_trace_logger_task_lifecycle(temp_log_dir):
    """Test trace logger task lifecycle methods."""
    trace_logger = TraceLogger(temp_log_dir)
    
    # Log task start
    trace_logger.log_task_start(
        task_id="task-123",
        intent="test intent",
        source="cli",
        metadata={"user": "test"}
    )
    
    # Log step
    trace_logger.log_step(
        task_id="task-123",
        step_id="step-1",
        step_name="planning",
        status="completed"
    )
    
    # Log task complete
    trace_logger.log_task_complete(
        task_id="task-123",
        result="success",
        duration_ms=1500,
        output={"result": "done"}
    )
    
    trace_file = trace_logger._get_trace_file()
    with open(trace_file, 'r') as f:
        lines = f.readlines()
    
    assert len(lines) == 3
    
    # Verify each event
    events = [json.loads(line) for line in lines]
    assert events[0]["event"] == "task_start"
    assert events[1]["event"] == "step"
    assert events[2]["event"] == "task_complete"


def test_trace_logger_daily_rotation(temp_log_dir):
    """Test that trace logger creates daily files with correct naming."""
    trace_logger = TraceLogger(temp_log_dir)
    
    trace_logger.log_trace({"event": "test1"})
    file1 = trace_logger._get_trace_file()
    
    # Verify file name format includes current date
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expected_name = f"task_{today}.jsonl"
    assert file1.name == expected_name
    assert file1.parent == trace_logger.log_dir


def test_global_audit_logger(temp_log_dir):
    """Test global audit logger getter."""
    reset_loggers()
    reset_config()
    
    # Set custom config
    from core.config import Config
    config = Config(base_dir=temp_log_dir)
    
    # Monkey-patch get_config to return our test config
    import core.config
    original_get_config = core.config.get_config
    core.config.get_config = lambda: config
    
    try:
        audit_logger = get_audit_logger()
        assert audit_logger is not None
        
        audit_logger.log(
            event_type="test",
            actor="test",
            action="test",
            result="success"
        )
        
        # Close handler to flush
        audit_logger.close()
        
        # Check file exists at the logger's audit_file path
        assert audit_logger.audit_file.exists()
    finally:
        core.config.get_config = original_get_config
        reset_loggers()


def test_global_trace_logger(temp_log_dir):
    """Test global trace logger getter."""
    reset_loggers()
    reset_config()
    
    # Set custom config
    from core.config import Config
    config = Config(base_dir=temp_log_dir)
    
    # Monkey-patch get_config
    import core.config
    original_get_config = core.config.get_config
    core.config.get_config = lambda: config
    
    try:
        trace_logger = get_trace_logger()
        assert trace_logger is not None
        
        trace_logger.log_trace({"event": "test"})
        
        trace_file = trace_logger._get_trace_file()
        assert trace_file.exists()
    finally:
        core.config.get_config = original_get_config
        reset_loggers()


def test_reset_loggers(temp_log_dir):
    """Test resetting global loggers."""
    audit_logger = AuditLogger(temp_log_dir)
    trace_logger = TraceLogger(temp_log_dir)
    
    # Set globals
    import core.logging_setup
    core.logging_setup._audit_logger = audit_logger
    core.logging_setup._trace_logger = trace_logger
    
    # Reset
    reset_loggers()
    
    # Globals should be None
    assert core.logging_setup._audit_logger is None
    assert core.logging_setup._trace_logger is None
