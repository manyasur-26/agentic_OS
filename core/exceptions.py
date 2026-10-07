"""
Custom exception hierarchy for Agentic OS.

Provides structured exception classes with context tracking,
JSON serialization, and meaningful error messages for all
components of the system.
"""

from typing import Any, Dict, Optional


class AgenticOSError(Exception):
    """
    Base exception for all Agentic OS errors.
    
    Attributes:
        message: Human-readable error message
        context: Additional contextual information as key-value pairs
    """
    
    def __init__(self, message: str, **context: Any) -> None:
        """
        Initialize the base exception.
        
        Args:
            message: Human-readable error message
            **context: Additional contextual information
        """
        self.message = message
        self.context = context
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """
        Format the message with context.
        
        Returns:
            Formatted message string
        """
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for JSON serialization.
        
        Returns:
            Dictionary with exception data
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "context": self.context
        }
    
    def __str__(self) -> str:
        """Return string representation with context."""
        return self._format_message()


class IntentBusError(AgenticOSError):
    """Base exception for Intent Bus errors."""
    pass


class IntentBusFullError(IntentBusError):
    """
    Raised when the intent bus queue is full and cannot accept more messages.
    
    This typically happens when subscribers are not processing messages
    fast enough, causing a backlog.
    """
    pass


class NoSubscriberError(IntentBusError):
    """
    Raised when a message is published but no subscribers are listening.
    
    This is particularly relevant for request/reply patterns where
    a response is expected but no component is subscribed to receive it.
    """
    pass


class IntentTimeoutError(IntentBusError):
    """
    Raised when waiting for a response to an intent times out.
    
    This occurs in request/reply patterns when the expected response
    does not arrive within the specified timeout period.
    """
    pass


class ConfigError(AgenticOSError):
    """Base exception for configuration errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """
    Raised when a required configuration file cannot be found.
    
    This typically happens when the system is started without
    proper configuration files in place.
    """
    pass


class ConfigValidationError(ConfigError):
    """
    Raised when configuration fails validation.
    
    This can occur due to:
    - Invalid YAML syntax
    - Missing required fields
    - Invalid data types
    - Out-of-range values
    """
    pass


class PolicyError(AgenticOSError):
    """Base exception for policy and security errors."""
    pass


class AccessDeniedError(PolicyError):
    """
    Raised when a policy denies access to a resource or action.
    
    This is a security-related error indicating that the requested
    operation violates the configured security policies.
    """
    pass


class CapabilityExpiredError(PolicyError):
    """
    Raised when a capability token has expired.
    
    Capability tokens have time-limited validity. This error
    indicates that the token being used is no longer valid.
    """
    pass


class SchedulerError(AgenticOSError):
    """Base exception for scheduler errors."""
    pass


class TaskTimeoutError(SchedulerError):
    """
    Raised when a task execution exceeds its time limit.
    
    This can happen when:
    - A task takes longer than its configured timeout
    - A dependency task hangs
    - Resource constraints prevent completion
    """
    pass


class DependencyCycleError(SchedulerError):
    """
    Raised when task dependencies form a cycle.
    
    A cyclic dependency makes it impossible to determine a valid
    execution order for tasks.
    """
    pass


class ToolError(AgenticOSError):
    """Base exception for tool-related errors."""
    pass


class ToolNotFoundError(ToolError):
    """
    Raised when a requested tool is not found in the registry.
    
    This can occur when:
    - The tool name is misspelled
    - The tool is not registered
    - The tool is disabled
    """
    pass


class ToolExecutionError(ToolError):
    """
    Raised when a tool fails during execution.
    
    This is a generic error for tool execution failures, which can
    include:
    - Invalid input parameters
    - External service failures
    - Permission issues
    - Resource constraints
    """
    pass


class MemoryError_(AgenticOSError):
    """
    Base exception for memory subsystem errors.
    
    Note: Trailing underscore to avoid shadowing the built-in MemoryError.
    """
    pass


class MemoryFullError(MemoryError_):
    """
    Raised when a memory tier is at capacity.
    
    This can happen when:
    - Working memory exceeds its LRU limit
    - Episodic memory database size limit is reached
    - Semantic memory index is full
    """
    pass


class MemoryNotFoundError(MemoryError_):
    """
    Raised when requested data is not found in memory.
    
    This can occur when:
    - A task ID has no associated traces
    - An embedding ID is invalid
    - A memory key does not exist
    """
    pass
