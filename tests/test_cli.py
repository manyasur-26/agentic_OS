"""
Unit tests for CLI.
"""

import pytest
import asyncio
import sys
from io import StringIO

from core.cli import CLI
from core.config import reset_config
from core.intent_bus import reset_intent_bus


@pytest.fixture
def cli():
    """Create a CLI instance for testing."""
    return CLI()


@pytest.mark.asyncio
async def test_cli_parser(cli):
    """Test CLI argument parser."""
    # Test status command
    args = cli.parser.parse_args(["status"])
    assert args.command == "status"
    assert args.json is False
    
    # Test status with JSON
    args = cli.parser.parse_args(["status", "--json"])
    assert args.json is True
    
    # Test submit command
    args = cli.parser.parse_args(["submit", "test intent"])
    assert args.command == "submit"
    assert args.intent == "test intent"
    assert args.priority == "normal"
    
    # Test submit with priority
    args = cli.parser.parse_args(["submit", "test", "--priority", "high"])
    assert args.priority == "high"
    
    # Test config command
    args = cli.parser.parse_args(["config", "--show"])
    assert args.command == "config"
    assert args.show is True
    
    # Test logs command
    args = cli.parser.parse_args(["logs", "--tail", "50"])
    assert args.command == "logs"
    assert args.tail == 50
    
    # Test version command
    args = cli.parser.parse_args(["version"])
    assert args.command == "version"


@pytest.mark.asyncio
async def test_cmd_version(cli):
    """Test version command."""
    args = cli.parser.parse_args(["version"])
    exit_code = await cli.cmd_version(args)
    
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cmd_status(cli):
    """Test status command."""
    reset_config()
    await reset_intent_bus()
    
    args = cli.parser.parse_args(["status"])
    exit_code = await cli.cmd_status(args)
    
    assert exit_code == 0


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_cmd_status_json(cli):
    """Test status command with JSON output."""
    from core.config import reset_config
    from core.intent_bus import reset_intent_bus
    
    reset_config()
    await reset_intent_bus()
    
    args = cli.parser.parse_args(["status", "--json"])
    
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    try:
        exit_code = await cli.cmd_status(args)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    
    assert exit_code == 0
    
    # Extract the last JSON object (in case log lines leaked)
    # start = output.find("{")
    # end = output.rfind("}") + 1
    # assert start != -1 and end > start, f"No JSON found in output: {output!r}"
   
    # lines = [l for l in output.strip().split("\n") if l.strip().startswith("{")]
    # assert len(lines) >= 1, f"No JSON found in output: {output!r}"
    # json_str = output[start:end]                                                                                                                
    import json
    data = None
    for line in reversed(output.strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                # Try to parse the whole thing from here to end
                start_idx = output.rfind("{")
                data = json.loads(output[start_idx:])
                break
            except json.JSONDecodeError:
                continue

    # Fallback: try full output
    if data is None:
        # Find the status JSON by looking for the marker "version"
        marker = '{"version"'
        idx = output.find(marker)
        if idx == -1:
            marker = '"version"'
            idx = output.find(marker)
            if idx != -1:
                idx = output.rfind("{", 0, idx)
        assert idx != -1, f"No status JSON found in output: {output!r}"
        # Find matching closing brace
        depth = 0
        for i in range(idx, len(output)):
            if output[i] == "{":
                depth += 1
            elif output[i] == "}":
                depth -= 1
                if depth == 0:
                    data = json.loads(output[idx:i+1])
                    break

    # data = json.loads(output[start:end])
    assert data is not None, f"Could not parse JSON from: {output!r}"
    assert data["version"] == "0.1.0-phase1"
    assert data["state"] == "running"
    assert "config" in data
    assert "intent_bus" in data
    assert "components" in data


@pytest.mark.asyncio
async def test_cmd_submit(cli):
    """Test submit command."""
    reset_config()
    await reset_intent_bus()
    
    args = cli.parser.parse_args(["submit", "test intent"])
    exit_code = await cli.cmd_submit(args)
    
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cmd_submit_with_priority(cli):
    """Test submit command with priority."""
    reset_config()
    await reset_intent_bus()
    
    args = cli.parser.parse_args([
        "submit", 
        "test intent",
        "--priority", "high",
        "--source", "test"
    ])
    exit_code = await cli.cmd_submit(args)
    
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cmd_config_show(cli):
    """Test config show command."""
    reset_config()
    
    args = cli.parser.parse_args(["config", "--show"])
    exit_code = await cli.cmd_config(args)
    
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cmd_config_validate(cli):
    """Test config validate command."""
    reset_config()
    
    args = cli.parser.parse_args(["config", "--validate"])
    exit_code = await cli.cmd_config(args)
    
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cmd_logs(cli, tmp_path):
    """Test logs command."""
    reset_config()
    
    # Create a fake log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "agentic-os.log"
    log_file.write_text("line1\nline2\nline3\n")
    
    # Monkey-patch config to use temp dir
    from core.config import Config
    config = Config(
        base_dir=str(tmp_path),
        logging=type('obj', (object,), {
            'log_dir': str(log_dir),
            'level': 'INFO',
            'format': 'text',
            'max_file_size': 1024,
            'backup_count': 5
        })()
    )
    
    import core.config
    original_get_config = core.config.get_config
    core.config.get_config = lambda: config
    
    try:
        args = cli.parser.parse_args(["logs", "--tail", "2"])
        exit_code = await cli.cmd_logs(args)
        
        assert exit_code == 0
    finally:
        core.config.get_config = original_get_config


@pytest.mark.asyncio
async def test_no_command(cli):
    """Test CLI with no command (shows help)."""
    args = cli.parser.parse_args([])
    exit_code = await cli.run(args)
    
    assert exit_code == 0
