"""
Unit tests for Intent Bus.
"""

import pytest
import asyncio
from datetime import datetime, timezone

from core.intent_bus import (
    IntentBus,
    IntentMessage,
    IntentType,
    Priority,
    get_intent_bus,
    reset_intent_bus
)


@pytest.fixture
async def bus():
    """Create a fresh intent bus for each test."""
    reset_intent_bus()
    bus = get_intent_bus()
    await bus.start()
    yield bus
    await bus.stop()


@pytest.mark.asyncio
async def test_subscribe_and_publish(bus):
    """Test basic subscribe and publish functionality."""
    # Subscribe to task requests
    queue = await bus.subscribe(IntentType.TASK_REQUEST)
    
    # Publish a message
    message = IntentMessage(
        source="test",
        type=IntentType.TASK_REQUEST,
        payload={"intent": "test intent"}
    )
    await bus.publish(message)
    
    # Receive the message
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    
    assert received.intent_id == message.intent_id
    assert received.source == "test"
    assert received.payload["intent"] == "test intent"


@pytest.mark.asyncio
async def test_multiple_subscribers(bus):
    """Test that multiple subscribers receive the same message."""
    queue1 = await bus.subscribe(IntentType.TASK_REQUEST)
    queue2 = await bus.subscribe(IntentType.TASK_REQUEST)
    
    message = IntentMessage(
        source="test",
        type=IntentType.TASK_REQUEST,
        payload={"data": "test"}
    )
    await bus.publish(message)
    
    # Both should receive
    received1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    received2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
    
    assert received1.intent_id == message.intent_id
    assert received2.intent_id == message.intent_id


@pytest.mark.asyncio
async def test_no_subscribers(bus):
    """Test publishing when no subscribers exist."""
    # Publish without any subscribers
    message = IntentMessage(
        source="test",
        type=IntentType.TASK_REQUEST,
        payload={"data": "test"}
    )
    await bus.publish(message)
    
    # Should not raise error
    assert bus.get_stats()["message_count"] == 1


@pytest.mark.asyncio
async def test_priority_routing(bus):
    """Test that priority is preserved in messages."""
    queue = await bus.subscribe(IntentType.TASK_REQUEST)
    
    message = IntentMessage(
        source="test",
        type=IntentType.TASK_REQUEST,
        payload={"data": "test"},
        priority=Priority.HIGH
    )
    await bus.publish(message)
    
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.priority == Priority.HIGH


@pytest.mark.asyncio
async def test_correlation_tracking(bus):
    """Test correlation ID tracking."""
    correlation_id = "test-correlation-123"
    
    message = IntentMessage(
        source="test",
        type=IntentType.TASK_REQUEST,
        payload={"data": "test"},
        correlation_id=correlation_id
    )
    await bus.publish(message)
    
    history = await bus.get_correlation_history(correlation_id)
    assert len(history) == 1
    assert history[0].intent_id == message.intent_id


@pytest.mark.asyncio
async def test_publish_immediate(bus):
    """Test the publish_immediate convenience method."""
    queue = await bus.subscribe(IntentType.TASK_REQUEST)
    
    message = await bus.publish_immediate(
        source="test",
        intent_type=IntentType.TASK_REQUEST,
        payload={"intent": "test"},
        priority=Priority.NORMAL
    )
    
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.intent_id == message.intent_id
    assert received.source == "test"


@pytest.mark.asyncio
async def test_message_serialization():
    """Test message to/from dict and JSON serialization."""
    message = IntentMessage(
        source="test",
        type=IntentType.TASK_REQUEST,
        payload={"data": "test"},
        priority=Priority.HIGH,
        correlation_id="corr-123"
    )
    
    # Test dict serialization
    data = message.to_dict()
    assert data["source"] == "test"
    assert data["type"] == "task_request"
    assert data["priority"] == 1
    
    # Test dict deserialization
    restored = IntentMessage.from_dict(data)
    assert restored.intent_id == message.intent_id
    assert restored.source == message.source
    assert restored.type == message.type
    
    # Test JSON serialization
    json_str = message.to_json()
    restored_json = IntentMessage.from_json(json_str)
    assert restored_json.intent_id == message.intent_id


@pytest.mark.asyncio
async def test_bus_stats(bus):
    """Test bus statistics."""
    queue = await bus.subscribe(IntentType.TASK_REQUEST)
    
    # Publish some messages
    for i in range(5):
        await bus.publish_immediate(
            source="test",
            intent_type=IntentType.TASK_REQUEST,
            payload={"index": i}
        )
    
    stats = bus.get_stats()
    assert stats["message_count"] == 5
    assert stats["dropped_count"] == 0
    assert "task_request" in stats["subscriber_counts"]


@pytest.mark.asyncio
async def test_unsubscribe(bus):
    """Test unsubscribing from intent types."""
    queue = await bus.subscribe(IntentType.TASK_REQUEST)
    
    # Publish and receive
    await bus.publish_immediate(
        source="test",
        intent_type=IntentType.TASK_REQUEST,
        payload={"data": "test1"}
    )
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received is not None
    
    # Unsubscribe
    await bus.unsubscribe(IntentType.TASK_REQUEST, queue)
    
    # Publish again
    await bus.publish_immediate(
        source="test",
        intent_type=IntentType.TASK_REQUEST,
        payload={"data": "test2"}
    )
    
    # Queue should be empty
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.1)


@pytest.mark.asyncio
async def test_queue_full_drops_message(bus):
    """Test that messages are dropped when queue is full."""
    # Create a bus with small queue size
    reset_intent_bus()
    small_bus = IntentBus(max_queue_size=2)
    await small_bus.start()
    
    queue = await small_bus.subscribe(IntentType.TASK_REQUEST)
    
    # Fill the queue
    await small_bus.publish_immediate(
        source="test",
        intent_type=IntentType.TASK_REQUEST,
        payload={"data": "1"}
    )
    await small_bus.publish_immediate(
        source="test",
        intent_type=IntentType.TASK_REQUEST,
        payload={"data": "2"}
    )
    
    # This should be dropped
    await small_bus.publish_immediate(
        source="test",
        intent_type=IntentType.TASK_REQUEST,
        payload={"data": "3"}
    )
    
    stats = small_bus.get_stats()
    assert stats["dropped_count"] == 1
    
    await small_bus.stop()
