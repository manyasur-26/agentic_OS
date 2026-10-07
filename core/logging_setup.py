"""
Logging setup for Agentic OS using structlog.

Provides structured logging with JSON/text formats, file rotation,
and proper integration with Python's logging module.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Optional
import structlog
from datetime import datetime, timezone

from .config import get_config, LoggingConfig


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """
    Configure structured logging for the entire application.
    
    Sets up both Python stdlib logging and structlog with:
    - Console output (JSON or text format)
    - File output with rotation
    - Consistent timestamp format
    - Component-level filtering
    
    Args:
        config: Optional LoggingConfig. If not provided, loads from global config.
    """
    if config is None:
        config = get_config().logging
    
    # Ensure log directory exists
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, config.level.upper()),
        stream=sys.stdout
    )
    
    # Remove default handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.level.upper()))
    
    # File handler with rotation
    log_file = log_dir / "agentic-os.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=config.max_file_size,
        backupCount=config.backup_count
    )
    file_handler.setLevel(getattr(logging, config.level.upper()))
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Configure structlog
    if config.format.lower() == "json":
        # JSON format for production
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, config.level.upper())
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Text format for development
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    exception_formatter=structlog.dev.plain_traceback
                )
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, config.level.upper())
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    # Log startup
    logger = structlog.get_logger()
    logger.info(
        "Logging initialized",
        level=config.level,
        format=config.format,
        log_file=str(log_file)
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger for a specific component.
    
    Args:
        name: Name of the component/module
        
    Returns:
        BoundLogger instance with component context
    """
    return structlog.get_logger(name).bind(component=name)


class AuditLogger:
    """
    Specialized logger for audit trail.
    
    Writes audit events to a separate append-only log file
    for security and compliance tracking.
    """
    
    def __init__(self, log_dir: str = "~/.agentic-os/traces"):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs
        """
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.log_dir / "audit.log"
        
        # Setup audit-specific file handler
        self._handler = logging.FileHandler(self.audit_file, mode='a')
        self._handler.setLevel(logging.INFO)
        self._handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        
        self._logger = logging.getLogger("audit")
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
    
    def log(self, 
            event_type: str,
            actor: str,
            action: str,
            target: Optional[str] = None,
            result: str = "success",
            details: Optional[dict] = None) -> None:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (e.g., "policy_check", "tool_execution")
            actor: Component or user performing the action
            action: The action being performed
            target: Optional target of the action
            result: Result of the action (success/failure/denied)
            details: Optional additional details
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "target": target,
            "result": result,
            "details": details or {}
        }
        
        import json
        self._logger.info(json.dumps(log_entry))
    
    def close(self) -> None:
        """Close the audit logger."""
        self._handler.close()


class TraceLogger:
    """
    Logger for task execution traces.
    
    Writes structured trace events to JSONL files for
    observability and debugging.
    """
    
    def __init__(self, log_dir: str = "~/.agentic-os/traces"):
        """
        Initialize trace logger.
        
        Args:
            log_dir: Directory for trace logs
        """
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Optional[Path] = None
        self._current_date: Optional[str] = None
    
    def _get_trace_file(self) -> Path:
        """
        Get the trace file for the current date.
        
        Returns:
            Path to today's trace file
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._current_date != today:
            self._current_date = today
        return self.log_dir / f"task_{self._current_date}.jsonl"
    
    def log_trace(self, trace_data: dict) -> None:
        """
        Log a trace event.
        
        Args:
            trace_data: Dictionary containing trace information
        """
        trace_file = self._get_trace_file()
        
        # Add timestamp if not present
        if "timestamp" not in trace_data:
            trace_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        import json
        with open(trace_file, 'a') as f:
            f.write(json.dumps(trace_data) + '\n')
    
    def log_task_start(self, 
                      task_id: str,
                      intent: str,
                      source: str,
                      metadata: Optional[dict] = None) -> None:
        """
        Log task start event.
        
        Args:
            task_id: Unique task identifier
            intent: Task intent/description
            source: Source of the task
            metadata: Optional additional metadata
        """
        self.log_trace({
            "event": "task_start",
            "task_id": task_id,
            "intent": intent,
            "source": source,
            "metadata": metadata or {}
        })
    
    def log_task_complete(self,
                         task_id: str,
                         result: str,
                         duration_ms: float,
                         output: Optional[dict] = None) -> None:
        """
        Log task completion event.
        
        Args:
            task_id: Unique task identifier
            result: Result status (success/failure/cancelled)
            duration_ms: Task duration in milliseconds
            output: Optional task output
        """
        self.log_trace({
            "event": "task_complete",
            "task_id": task_id,
            "result": result,
            "duration_ms": duration_ms,
            "output": output or {}
        })
    
    def log_step(self,
                task_id: str,
                step_id: str,
                step_name: str,
                status: str,
                details: Optional[dict] = None) -> None:
        """
        Log a step execution event.
        
        Args:
            task_id: Parent task identifier
            step_id: Step identifier
            step_name: Name of the step
            status: Step status (started/running/completed/failed)
            details: Optional step details
        """
        self.log_trace({
            "event": "step",
            "task_id": task_id,
            "step_id": step_id,
            "step_name": step_name,
            "status": status,
            "details": details or {}
        })


# Global instances
_audit_logger: Optional[AuditLogger] = None
_trace_logger: Optional[TraceLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance.
    
    Returns:
        AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        config = get_config()
        _audit_logger = AuditLogger(str(Path(config.base_dir) / "traces"))
    return _audit_logger


def get_trace_logger() -> TraceLogger:
    """
    Get the global trace logger instance.
    
    Returns:
        TraceLogger instance
    """
    global _trace_logger
    if _trace_logger is None:
        config = get_config()
        _trace_logger = TraceLogger(str(Path(config.base_dir) / "traces"))
    return _trace_logger


def reset_loggers() -> None:
    """Reset global loggers (mainly for testing)."""
    global _audit_logger, _trace_logger
    if _audit_logger:
        _audit_logger.close()
    _audit_logger = None
    _trace_logger = None
