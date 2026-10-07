"""
Intent Bus - Core pub/sub messaging system for Agentic OS.

All components communicate exclusively through this bus using asyncio queues.
Supports priority-based routing, correlation tracking, and optional ZeroMQ integration.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import json
import logging
# from .logging_setup import get_logger

from .exceptions import (
    IntentBusError,
    IntentBusFullError,
    NoSubscriberError,
    IntentTimeoutError
)

# logger = get_logger("intent_bus")
logger = logging.getLogger("agentic_os.intent_bus")


class IntentType(Enum):
    """Types of intents that can flow through the bus."""
    VOICE_COMMAND = "voice_command"
    CLI_COMMAND = "cli_command"
    SYSTEM_EVENT = "system_event"
    TASK_REQUEST = "task_request"
    TASK_UPDATE = "task_update"
    TOOL_RESULT = "tool_result"
    POLICY_CHECK = "policy_check"
    MEMORY_QUERY = "memory_query"
    MEMORY_STORE = "memory_store"
    SCHEDULER_SIGNAL = "scheduler_signal"
    OBSERVABILITY = "observability"


class Priority(Enum):
    """Priority levels for intent messages."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class IntentMessage:
    """
    Message format for all intents flowing through the bus.
    
    Attributes:
        intent_id: Unique identifier for this intent
        source: Component that generated this intent
        type: IntentType enum
        payload: Actual data/content of the intent
        timestamp: UTC timestamp when created
        priority: Priority level for routing
        correlation_id: Optional ID to track related intents
        metadata: Additional contextual information
    """
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    type: IntentType = IntentType.TASK_REQUEST
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: Priority = Priority.NORMAL
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            "intent_id": self.intent_id,
            "source": self.source,
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentMessage":
        """Create message from dictionary."""
        return cls(
            intent_id=data["intent_id"],
            source=data["source"],
            type=IntentType(data["type"]),
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=Priority(data["priority"]),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {})
        )
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "IntentMessage":
        """Create message from JSON string."""
        return cls.from_dict(json.loads(json_str))


class IntentBus:
    """
    Asyncio-based pub/sub intent bus.
    
    Components subscribe to specific intent types and receive messages
    through asyncio queues. Supports priority-based delivery and correlation
    tracking.
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize the intent bus.
        
        Args:
            max_queue_size: Maximum number of messages per subscriber queue
        """
        self._subscribers: Dict[IntentType, List[asyncio.Queue]] = {}
        self._max_queue_size = max_queue_size
        self._running = False
        self._message_count = 0
        self._dropped_count = 0
        self._lock = asyncio.Lock()
        
        # For correlation tracking
        self._correlations: Dict[str, List[IntentMessage]] = {}
        
        logger.info("IntentBus initialized with max_queue_size=%d", max_queue_size)
    
    async def subscribe(self, intent_type: IntentType) -> asyncio.Queue:
        """
        Subscribe to a specific intent type.
        
        Args:
            intent_type: The type of intent to subscribe to
            
        Returns:
            asyncio.Queue that will receive messages of this type
        """
        async with self._lock:
            if intent_type not in self._subscribers:
                self._subscribers[intent_type] = []
            
            queue = asyncio.Queue(maxsize=self._max_queue_size)
            self._subscribers[intent_type].append(queue)
            logger.debug("New subscriber for %s (total: %d)", 
                        intent_type.value, len(self._subscribers[intent_type]))
            return queue
    
    async def unsubscribe(self, intent_type: IntentType, queue: asyncio.Queue) -> None:
        """
        Unsubscribe a queue from an intent type.
        
        Args:
            intent_type: The intent type to unsubscribe from
            queue: The queue to remove
        """
        async with self._lock:
            if intent_type in self._subscribers:
                if queue in self._subscribers[intent_type]:
                    self._subscribers[intent_type].remove(queue)
                    logger.debug("Unsubscribed from %s", intent_type.value)
    
    async def publish(self, message: IntentMessage, require_subscriber: bool = False) -> None:
        """
         Publish a message to all subscribers of its type.

        Args:
            message: The IntentMessage to publish.
            require_subscriber: If True, raise NoSubscriberError when no
                subscribers exist, and raise IntentBusFullError instead of
                silently dropping when a queue is full.

        Raises:
            NoSubscriberError: When require_subscriber=True and no subscribers.
            IntentBusFullError: When require_subscriber=True and a subscriber
                queue is full.
            IntentBusError: When publishing fails for any other reason.
        """
        if not self._running:
            logger.warning("Attempted to publish while bus not running")
            return
        
        self._message_count += 1
        
        # Track correlation if present
        if message.correlation_id:
            if message.correlation_id not in self._correlations:
                self._correlations[message.correlation_id] = []
            self._correlations[message.correlation_id].append(message)
        
        # Get subscribers for this message type
        async with self._lock:
            subscribers = self._subscribers.get(message.type, []).copy()
        
        if not subscribers:
            if require_subscriber:
                raise NoSubscriberError(
                    f"No subscribers for intent type {message.type.value}",
                    intent_type=message.type.value,
                    intent_id=message.intent_id
                )
            logger.debug("No subscribers for %s", message.type.value)
            return
        
        # Publish to all subscribers
                # Publish to all subscribers
        for queue in subscribers:
            try:
                await asyncio.wait_for(queue.put(message), timeout=0.1)
            except asyncio.TimeoutError:
                self._dropped_count += 1
                logger.warning(
                    "Dropped message: subscriber queue full (intent_id=%s, intent_type=%s, queue_size=%d)",
                    message.intent_id,
                    message.type.value,
                    self._max_queue_size
                )
                # Strict mode: raise instead of silently dropping
                if require_subscriber:
                    raise IntentBusFullError(
                        f"Subscriber queue full for message {message.intent_id}",
                        intent_id=message.intent_id,
                        intent_type=message.type.value,
                        queue_size=self._max_queue_size,
                    )
            except asyncio.CancelledError:
                # Don't swallow cancellation — propagate for clean shutdown
                raise
            except Exception as e:
                logger.error("Error publishing to queue: %s", e)
                raise IntentBusError(
                    f"Error publishing message {message.intent_id}",
                    intent_id=message.intent_id,
                    original_error=str(e),
                ) from e

        logger.debug("Published %s to %d subscribers", 
                    message.intent_id, len(subscribers))
    
    async def publish_immediate(self, 
                                source: str,
                                intent_type: IntentType,
                                payload: Dict[str, Any],
                                priority: Priority = Priority.NORMAL,
                                correlation_id: Optional[str] = None,
                                require_subscriber: bool = False) -> IntentMessage:
        """
        Convenience method to create and publish a message immediately.
        
        Args:
            source: Component generating the intent
            intent_type: Type of intent
            payload: Message payload
            priority: Priority level
            correlation_id: Optional correlation ID
            require_subscriber: If True, raise NoSubscriberError when no subscribers exist
            
        Returns:
            The created IntentMessage
            
        Raises:
            IntentBusFullError: When subscriber queue is full
            NoSubscriberError: When require_subscriber=True and no subscribers exist
        """
        message = IntentMessage(
            source=source,
            type=intent_type,
            payload=payload,
            priority=priority,
            correlation_id=correlation_id
        )
        await self.publish(message, require_subscriber=require_subscriber)
        return message
    
    async def request_reply(self,
                           request_type: IntentType,
                           response_type: IntentType,
                           payload: Dict[str, Any],
                           source: str,
                           timeout: float = 5.0) -> IntentMessage:
        """
        Send a request and wait for a response using correlation tracking.
        
        Args:
            request_type: Type of the request intent
            response_type: Type of the expected response intent
            payload: Request payload
            source: Component making the request
            timeout: Maximum time to wait for response in seconds
            
        Returns:
            The response IntentMessage
            
        Raises:
            IntentTimeoutError: When no response arrives within timeout
            NoSubscriberError: When no subscribers are listening for the request
        """
        correlation_id = str(uuid.uuid4())
        
        # Subscribe to response type
        response_queue = await self.subscribe(response_type)
        
        try:
            # Publish request
            await self.publish_immediate(
                source=source,
                intent_type=request_type,
                payload=payload,
                correlation_id=correlation_id,
                require_subscriber=True
            )
            
            # Wait for response
            try:
                response = await asyncio.wait_for(
                    response_queue.get(),
                    timeout=timeout
                )
                
                # Verify correlation ID matches
                if response.correlation_id != correlation_id:
                    logger.warning(
                        "Received response with mismatched correlation ID: %s != %s",
                        response.correlation_id, correlation_id
                    )
                
                return response
                
            except asyncio.TimeoutError:
                raise IntentTimeoutError(
                    f"No response received within {timeout}s",
                    correlation_id=correlation_id,
                    request_type=request_type.value,
                    response_type=response_type.value,
                    timeout=timeout
                )
        finally:
            # Clean up subscription
            await self.unsubscribe(response_type, response_queue)
    
    async def get_correlation_history(self, correlation_id: str) -> List[IntentMessage]:
        """
        Get all messages associated with a correlation ID.
        
        Args:
            correlation_id: The correlation ID to look up
            
        Returns:
            List of messages with this correlation ID
        """
        return self._correlations.get(correlation_id, []).copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get bus statistics.
        
        Returns:
            Dictionary with bus metrics
        """
        return {
            "running": self._running,
            "message_count": self._message_count,
            "dropped_count": self._dropped_count,
            "subscriber_counts": {
                t.value: len(queues) 
                for t, queues in self._subscribers.items()
            },
            "active_correlations": len(self._correlations)
        }
    
    async def start(self) -> None:
        """Start the intent bus."""
        self._running = True
        logger.info("IntentBus started")
    
    async def stop(self) -> None:
        """Stop the intent bus and clear queues."""
        self._running = False
        
        # Clear all queues
        async with self._lock:
            for queues in self._subscribers.values():
                for queue in queues:
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
            self._subscribers.clear()
        
        logger.info("IntentBus stopped. Total messages: %d, Dropped: %d",
                   self._message_count, self._dropped_count)


# Global bus instance
_global_bus: Optional[IntentBus] = None


def get_intent_bus() -> IntentBus:
    """
    Get the global intent bus instance.
    
    Returns:
        The global IntentBus instance
    """
    global _global_bus
    if _global_bus is None:
        _global_bus = IntentBus()
    return _global_bus


async def reset_intent_bus() -> None:
    """Reset the global intent bus (mainly for testing)."""
    global _global_bus
    if _global_bus is not None:
        await _global_bus.stop()
    _global_bus = IntentBus()
