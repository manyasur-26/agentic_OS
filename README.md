# Agentic OS - Userspace Sandwich Layer

An intelligent operating system layer that sits between applications and an untouched Linux kernel, transforming a normal OS into an agentic one through planning, persistent memory, policy enforcement, scheduling, and voice I/O.

## Architecture Overview

Agentic OS is built as a 7-layer architecture that runs entirely in userspace using standard Linux syscalls (cgroups v2, namespaces, seccomp, Landlock, inotify, DBus, netlink). No kernel modifications are required.

### The 7 Layers

1. **Input Modalities** - Voice, CLI, system events → Intent Bus
2. **Intent Bus** - Pub/sub messaging core (asyncio queues)
3. **Cognitive Core** - Planner (Qwen 2.5), Memory (3-tier), Policy Engine
4. **Meta-Scheduler** - Priority scoring, DAG execution, cgroup mapping
5. **Tool Layer** - Registry, semantic routing, sandboxed execution
6. **Observability** - Traces, audit logs, metrics, dashboards
7. **Kernel Interface** - Read-only use of standard syscalls

## Phase 1: Foundation (COMPLETE)

Phase 1 establishes the foundational infrastructure for the entire system. All components are production-quality with comprehensive testing.

### What Was Built

#### 1. Intent Bus (`core/intent_bus.py`)
- **Purpose**: Core pub/sub messaging system for all component communication
- **Features**:
  - Asyncio-based queue implementation
  - Priority-based message routing (CRITICAL, HIGH, NORMAL, LOW, BACKGROUND)
  - Correlation ID tracking for request/response patterns
  - Message serialization (JSON/dict)
  - Statistics tracking (message count, drops, subscribers)
  - ZeroMQ-ready architecture (for future external integration)
- **Key Classes**:
  - `IntentMessage`: Standardized message format with intent_id, source, type, payload, timestamp, priority, correlation_id
  - `IntentBus`: Pub/sub implementation with subscribe/publish methods
  - `IntentType`: Enum of all intent types (VOICE_COMMAND, CLI_COMMAND, TASK_REQUEST, etc.)
  - `Priority`: Enum for priority levels

#### 2. Configuration Loader (`core/config.py`)
- **Purpose**: Load, validate, and manage YAML configuration
- **Features**:
  - Environment variable interpolation (`${VAR_NAME}` syntax)
  - Default value support
  - Multiple config file merging
  - Type-safe dataclasses for all config sections
  - Path expansion for `~` and environment variables
- **Key Classes**:
  - `Config`: Main configuration container
  - `ConfigLoader`: File loading and validation
  - `PlannerConfig`, `MemoryConfig`, `SchedulerConfig`, `VoiceConfig`, `LoggingConfig`: Section-specific configs

#### 3. Logging Setup (`core/logging_setup.py`)
- **Purpose**: Structured logging with audit and trace capabilities
- **Features**:
  - Structlog integration for structured logging
  - JSON and text format support
  - File rotation (RotatingFileHandler)
  - Component-level filtering
  - Separate audit logger (append-only for security)
  - Trace logger for task execution (JSONL format)
- **Key Classes**:
  - `AuditLogger`: Security audit trail
  - `TraceLogger`: Task execution traces with daily rotation
  - `setup_logging()`: Initialize logging system

#### 4. CLI (`core/cli.py`)
- **Purpose**: User-facing command-line interface
- **Commands**:
  - `agentic-os status`: Show system status (JSON/text)
  - `agentic-os submit "intent"`: Submit a task with priority
  - `agentic-os config --show/--validate`: View/validate configuration
  - `agentic-os logs --tail N`: View system logs
  - `agentic-os version`: Show version information
- **Features**:
  - Async command execution
  - Priority-based task submission
  - JSON output option for status
  - Component-level log filtering

#### 5. systemd Services (`systemd/`)
- **agentic-os.service**: Main daemon service
  - Runs `core/main.py`
  - Auto-restart on failure
  - Security hardening (NoNewPrivileges, ProtectSystem, ProtectHome)
  - Cgroup integration
- **agentic-voice.service**: Voice daemon (Phase 6)
  - Audio device access
  - PartOf main service for lifecycle management

#### 6. Main Daemon (`core/main.py`)
- **Purpose**: Entry point for the systemd service
- **Features**:
  - Lifecycle management (initialize, run, shutdown)
  - Signal handling (SIGTERM, SIGINT)
  - Component orchestration (expanded in later phases)
  - Graceful shutdown

### Configuration Files

#### `config.yaml`
Main configuration file with sections for:
- Planner (model names, Ollama host, temperature)
- Memory (working size, database paths, FAISS config)
- Scheduler (workers, cgroups, priority weights)
- Voice (wake word, VAD threshold, STT/TTS models)
- Logging (level, format, rotation)

#### `policy.yaml`
Security and access control policies:
- Resource access rules (filesystem, network, shell)
- Capability tokens (ed25519-based authorization)
- Tool-specific policies
- Audit configuration
- Sandbox settings (Landlock, seccomp, namespaces)

#### `tools/registry.yaml`
Tool registry defining available tools:
- Tool definitions with schemas
- Sandbox requirements per tool
- Policy constraints
- Tool groups for semantic routing
- I/O schemas for validation

### Unit Tests

Comprehensive test coverage for all Phase 1 components:

- `tests/test_intent_bus.py`: 11 tests covering subscribe/publish, priority, correlation, serialization
- `tests/test_config.py`: 13 tests covering loading, validation, env interpolation, defaults
- `tests/test_logging_setup.py`: 11 tests covering setup, audit logger, trace logger
- `tests/test_cli.py`: 8 tests covering all CLI commands

Run tests with:
```bash
pytest tests/ -v
```

### Verification Script

`test_phase1.py` is a comprehensive verification script that:
- Validates file structure
- Tests configuration loading
- Tests intent bus functionality
- Tests logging setup
- Tests CLI commands
- Validates systemd service files
- Runs unit tests

Run with:
```bash
python test_phase1.py
```

## Installation

### Prerequisites
- Python 3.11+
- Linux (Debian 12 / Ubuntu 22.04+)
- Systemd (for service management)

### Dependencies
```bash
pip install pyyaml structlog
# For testing:
pip install pytest pytest-asyncio
```

### Setup

1. Clone or copy the project to `~/.agentic-os/`
2. Install dependencies
3. Copy config files to appropriate locations
4. (Optional) Install systemd user services:

```bash
cp systemd/agentic-os.service ~/.config/systemd/user/
cp systemd/agentic-voice.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable agentic-os.service
systemctl --user start agentic-os.service
```

## Usage

### CLI Commands

```bash
# Check system status
python core/cli.py status

# Submit a task
python core/cli.py submit "Summarize the PDF in Downloads"

# Submit with high priority
python core/cli.py submit "Urgent task" --priority high

# View configuration
python core/cli.py config --show

# Validate configuration
python core/cli.py config --validate

# View logs
python core/cli.py logs --tail 50

# View version
python core/cli.py version
```

### Programmatic Usage

```python
import asyncio
from core import get_intent_bus, IntentType, Priority, get_config

async def main():
    # Get configuration
    config = get_config()
    
    # Get and start intent bus
    bus = get_intent_bus()
    await bus.start()
    
    # Subscribe to task requests
    queue = await bus.subscribe(IntentType.TASK_REQUEST)
    
    # Publish a message
    await bus.publish_immediate(
        source="my_app",
        intent_type=IntentType.TASK_REQUEST,
        payload={"intent": "Do something"},
        priority=Priority.NORMAL
    )
    
    # Receive messages
    message = await queue.get()
    print(f"Received: {message.payload}")
    
    await bus.stop()

asyncio.run(main())
```

## File Structure

```
~/.agentic-os/
├── config.yaml              # Main configuration
├── policy.yaml              # Security policies
├── test_phase1.py          # Phase 1 verification script
├── core/
│   ├── __init__.py         # Package exports
│   ├── intent_bus.py       # Pub/sub messaging
│   ├── config.py           # Configuration loader
│   ├── logging_setup.py    # Logging infrastructure
│   ├── cli.py              # Command-line interface
│   └── main.py             # Daemon entry point
├── tools/
│   └── registry.yaml       # Tool definitions
├── systemd/
│   ├── agentic-os.service  # Main daemon service
│   └── agentic-voice.service  # Voice daemon
├── tests/
│   ├── __init__.py
│   ├── test_intent_bus.py
│   ├── test_config.py
│   ├── test_logging_setup.py
│   └── test_cli.py
├── voice/                  # (Phase 6)
├── memory/                 # (Phase 2)
├── working/                # (Phase 2)
├── traces/                 # (Phase 5)
├── checkpoints/            # (Phase 5)
├── plans/                  # (Phase 2)
├── prompts/                # (Phase 2)
└── logs/                   # Created at runtime
```

## Next Steps

Phase 1 is complete. The foundation is in place for:

**Phase 2 - Planner + Memory**
- Ollama client wrapper
- Planner with decomposer + critic loop
- Working memory (in-RAM)
- Episodic memory (SQLite + FAISS)
- Semantic memory (SQLite + FAISS)

**Phase 3 - Tools + Policy**
- Tool registry implementation
- File ops tool
- Shell tool with sandbox
- Policy engine enforcement
- Audit log integration

**Phase 4 - Scheduler**
- Priority scoring
- Worker pool
- Dependency DAG
- Cgroup integration

**Phase 5 - Observability**
- Trace store
- Metrics endpoint
- Live dashboard
- Rollback system

**Phase 6 - Voice**
- OpenWakeWord integration
- Silero VAD
- faster-whisper STT
- Piper TTS

**Phase 7 - Advanced**
- Landlock + seccomp sandbox
- Capability tokens
- Multi-agent coordination
- Offline mode
- ISO build

## Design Principles

1. **No Kernel Modifications**: Everything runs in userspace
2. **Async-First**: All I/O uses asyncio
3. **Type Safety**: Type hints everywhere, dataclasses/Pydantic for models
4. **Config-Driven**: No hardcoded paths or values
5. **Test Coverage**: Every module has unit tests
6. **Observability**: Structured logging, traces, audit logs
7. **Security**: Policy enforcement, sandboxing, audit trails
8. **Extensibility**: Plugin-based tool system, semantic routing

## License

All components use permissive licenses:
- Code: MIT/Apache 2.0
- Models: Apache 2.0 (Qwen 2.5)
- Voice: MIT/Apache 2.0 (OpenWakeWord, Silero, faster-whisper)
- Memory: MIT/Public Domain (FAISS, SQLite)

## Contributing

Phase 1 is complete. Proceed to Phase 2 implementation when ready.
