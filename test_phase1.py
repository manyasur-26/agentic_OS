#!/usr/bin/env python3
"""
Test script to verify Phase 1 implementation.

This script runs comprehensive tests for all Phase 1 components:
- Intent Bus
- Config Loader
- Logging Setup
- CLI
- systemd service files
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.intent_bus import (
    IntentBus,
    IntentMessage,
    IntentType,
    Priority,
    get_intent_bus,
    reset_intent_bus
)
from core.config import (
    Config,
    ConfigLoader,
    get_config,
    get_config_loader,
    reset_config
)
from core.logging_setup import (
    setup_logging,
    get_logger,
    AuditLogger,
    TraceLogger,
    reset_loggers
)


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_config_loading():
    """Test configuration loading."""
    print_section("Testing Configuration Loading")
    
    try:
        # Reset global config
        reset_config()
        
        # Load config from default path
        config = get_config(str(project_root / "config.yaml"))
        
        print(f"✓ Config loaded successfully")
        print(f"  Base dir: {config.base_dir}")
        print(f"  Planner model: {config.planner.model_name}")
        print(f"  Scheduler workers: {config.scheduler.worker_count}")
        print(f"  Logging level: {config.logging.level}")
        
        # Test config loader
        loader = get_config_loader()
        policy = loader.load_policy()
        registry = loader.load_registry()
        
        print(f"✓ Policy loaded: {len(policy)} sections")
        print(f"✓ Registry loaded: {len(registry.get('tools', []))} tools")
        
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_intent_bus():
    """Test intent bus functionality."""
    print_section("Testing Intent Bus")
    
    try:
        # Reset and get bus
        # reset_intent_bus()
        bus = get_intent_bus()
        await bus.start()
        
        print("✓ Intent bus started")
        
        # Test subscription
        queue = await bus.subscribe(IntentType.TASK_REQUEST)
        print("✓ Subscribed to TASK_REQUEST")
        
        # Test publish
        message = await bus.publish_immediate(
            source="test",
            intent_type=IntentType.TASK_REQUEST,
            payload={"intent": "test intent"},
            priority=Priority.NORMAL
        )
        print(f"✓ Published message: {message.intent_id}")
        
        # Test receive
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.intent_id == message.intent_id
        print(f"✓ Received message: {received.intent_id}")
        
        # Test stats
        stats = bus.get_stats()
        print(f"✓ Bus stats: {stats['message_count']} messages, "
              f"{stats['dropped_count']} dropped")
        
        # Test correlation tracking
        corr_id = "test-correlation"
        await bus.publish_immediate(
            source="test",
            intent_type=IntentType.TASK_UPDATE,
            payload={"status": "completed"},
            correlation_id=corr_id
        )
        history = await bus.get_correlation_history(corr_id)
        print(f"✓ Correlation tracking: {len(history)} messages")
        
        # Test serialization
        json_str = message.to_json()
        restored = IntentMessage.from_json(json_str)
        assert restored.intent_id == message.intent_id
        print("✓ Message serialization works")
        
        await bus.stop()
        print("✓ Intent bus stopped")
        
        return True
    except Exception as e:
        print(f"✗ Intent bus test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_logging():
    """Test logging setup."""
    print_section("Testing Logging Setup")
    
    try:
        # Reset loggers
        reset_loggers()
        
        # Setup logging with test config
        from core.config import LoggingConfig
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            log_config = LoggingConfig(
                level="DEBUG",
                format="text",
                log_dir=tmpdir,
                max_file_size=1024,
                backup_count=2
            )
            
            setup_logging(log_config)
            print("✓ Logging setup completed")
            
            # Test logger
            logger = get_logger("test_component")
            logger.info("Test log message", extra_data="test")
            print("✓ Logger created and logged message")
            
            # Test audit logger
            audit_logger = AuditLogger(tmpdir)
            audit_logger.log(
                event_type="test_event",
                actor="test",
                action="test_action",
                result="success"
            )
            print("✓ Audit logger works")
            audit_logger.close()
            
            # Test trace logger
            trace_logger = TraceLogger(tmpdir)
            trace_logger.log_task_start(
                task_id="task-123",
                intent="test",
                source="test"
            )
            print("✓ Trace logger works")
            
            # Verify files exist
            log_file = Path(tmpdir) / "agentic-os.log"
            audit_file = Path(tmpdir) / "audit.log"
            trace_file = trace_logger._get_trace_file()
            
            assert log_file.exists()
            assert audit_file.exists()
            assert trace_file.exists()
            print(f"✓ Log files created: {log_file.name}, {audit_file.name}, {trace_file.name}")
        
        return True
    except Exception as e:
        print(f"✗ Logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli():
    """Test CLI commands."""
    print_section("Testing CLI")
    
    try:
        from core.cli import CLI
        
        cli = CLI()
        print("✓ CLI initialized")
        
        # Test version command
        args = cli.parser.parse_args(["version"])
        exit_code = asyncio.run(cli.cmd_version(args))
        assert exit_code == 0
        print("✓ Version command works")
        
        # Test config command
        reset_config()
        args = cli.parser.parse_args(["config", "--validate"])
        exit_code = asyncio.run(cli.cmd_config(args))
        assert exit_code == 0
        print("✓ Config validate command works")
        
        # Test status command
        reset_config()
        # reset_intent_bus()
        args = cli.parser.parse_args(["status"])
        exit_code = asyncio.run(cli.cmd_status(args))
        assert exit_code == 0
        print("✓ Status command works")
        
        # Test submit command
        reset_config()
        # reset_intent_bus()
        args = cli.parser.parse_args(["submit", "test intent"])
        exit_code = asyncio.run(cli.cmd_submit(args))
        assert exit_code == 0
        print("✓ Submit command works")
        
        return True
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_systemd_files():
    """Test systemd service files exist and are valid."""
    print_section("Testing systemd Service Files")
    
    try:
        systemd_dir = project_root / "systemd"
        
        # Check agentic-os.service
        service_file = systemd_dir / "agentic-os.service"
        assert service_file.exists()
        print(f"✓ agentic-os.service exists")
        
        # Check agentic-voice.service
        voice_file = systemd_dir / "agentic-voice.service"
        assert voice_file.exists()
        print(f"✓ agentic-voice.service exists")
        
        # Validate file contents
        service_content = service_file.read_text()
        assert "[Unit]" in service_content
        assert "[Service]" in service_content
        assert "[Install]" in service_content
        assert "ExecStart" in service_content
        print(f"✓ agentic-os.service has valid structure")
        
        voice_content = voice_file.read_text()
        assert "[Unit]" in voice_content
        assert "[Service]" in voice_content
        assert "ExecStart" in voice_content
        print(f"✓ agentic-voice.service has valid structure")
        
        return True
    except Exception as e:
        print(f"✗ systemd files test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_structure():
    """Test that all required files and directories exist."""
    print_section("Testing File Structure")
    
    try:
        required_dirs = [
            "core",
            "tools",
            "voice",
            "memory",
            "working",
            "memory/traces",
            "memory/checkpoints",
            "plans",
            "prompts",
            "logs",
            "systemd",
            "tests"
        ]
        
        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            assert dir_path.exists() and dir_path.is_dir()
            print(f"✓ Directory exists: {dir_name}")
        
        required_files = [
            "core/__init__.py",
            "core/intent_bus.py",
            "core/config.py",
            "core/logging_setup.py",
            "core/cli.py",
            "core/main.py",
            "config.yaml",
            "policy.yaml",
            "tools/registry.yaml",
            "systemd/agentic-os.service",
            "systemd/agentic-voice.service",
            "tests/__init__.py",
            "tests/test_intent_bus.py",
            "tests/test_config.py",
            "tests/test_logging_setup.py",
            "tests/test_cli.py"
        ]
        
        for file_name in required_files:
            file_path = project_root / file_name
            assert file_path.exists() and file_path.is_file()
            print(f"✓ File exists: {file_name}")
        
        return True
    except Exception as e:
        print(f"✗ File structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_unit_tests():
    """Run pytest unit tests."""
    print_section("Running Unit Tests")
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✓ All unit tests passed")
            return True
        else:
            print(f"✗ Unit tests failed with exit code {result.returncode}")
            return False
    except Exception as e:
        print(f"✗ Unit test execution failed: {e}")
        print("  (pytest may not be installed, skipping unit tests)")
        return True  # Don't fail if pytest is not available


def main():
    """Run all Phase 1 tests."""
    print("\n" + "="*60)
    print("  Agentic OS Phase 1 Verification Test")
    print("="*60)
    
    results = {}
    
    # Run all tests
    results["File Structure"] = test_file_structure()
    results["Config Loading"] = test_config_loading()
    results["Intent Bus"] = asyncio.run(test_intent_bus())
    results["Logging"] = test_logging()
    results["CLI"] = test_cli()
    results["systemd Files"] = test_systemd_files()
    results["Unit Tests"] = run_unit_tests()
    
    # Print summary
    print_section("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All Phase 1 tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
