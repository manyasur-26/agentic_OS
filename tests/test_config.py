"""
Unit tests for Config Loader.
"""

import pytest
import os
import tempfile
from pathlib import Path

from core.config import (
    Config,
    ConfigLoader,
    PlannerConfig,
    MemoryConfig,
    SchedulerConfig,
    VoiceConfig,
    LoggingConfig,
    get_config,
    get_config_loader,
    reset_config
)


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
base_dir: /tmp/test-agentic-os
planner:
  model_name: qwen2.5:7b
  critic_model: qwen2.5:1.5b
  ollama_host: http://localhost:11434
  max_iterations: 3
  temperature: 0.7
  timeout: 30
memory:
  working_memory_size: 1000
  episodic_db_path: ~/.agentic-os/memory/episodic.db
  semantic_db_path: ~/.agentic-os/memory/semantic.db
  faiss_index_dim: 768
  faiss_index_type: flat
scheduler:
  worker_count: 4
  cgroup_path: /sys/fs/cgroup
  urgent_slice: urgent.slice
  normal_slice: normal.slice
  background_slice: background.slice
  priority_weights:
    urgency: 1.0
    deadline: 0.8
    importance: 0.6
    cost: 0.4
voice:
  wake_word_model: hey_jarvis
  vad_threshold: 0.5
  stt_model: base
  tts_model: en_US-lessac-medium
  audio_device: null
logging:
  level: INFO
  format: json
  log_dir: ~/.agentic-os/logs
  max_file_size: 10485760
  backup_count: 5
""")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_config_with_env():
    """Create a config file with environment variable interpolation."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
base_dir: ${HOME}/.agentic-os
planner:
  ollama_host: ${OLLAMA_HOST:-http://localhost:11434}
""")
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_load_yaml_success(temp_config_file):
    """Test successful YAML loading."""
    loader = ConfigLoader(temp_config_file)
    data = loader.load_yaml(temp_config_file)
    
    assert data["base_dir"] == "/tmp/test-agentic-os"
    assert data["planner"]["model_name"] == "qwen2.5:7b"
    assert data["scheduler"]["worker_count"] == 4


def test_load_yaml_not_found():
    """Test loading non-existent file."""
    loader = ConfigLoader("/nonexistent/path/config.yaml")
    with pytest.raises(FileNotFoundError):
        loader.load_yaml("/nonexistent/path/config.yaml")


def test_env_var_interpolation(temp_config_with_env):
    """Test environment variable interpolation."""
    # Set test environment variable
    os.environ["HOME"] = "/tmp/testhome"
    os.environ["OLLAMA_HOST"] = "http://custom-host:11434"
    
    loader = ConfigLoader(temp_config_with_env)
    data = loader.load_yaml(temp_config_with_env)
    
    assert data["base_dir"] == "/tmp/testhome/.agentic-os"
    assert data["planner"]["ollama_host"] == "http://custom-host:11434"
    
    # Cleanup
    del os.environ["HOME"]
    del os.environ["OLLAMA_HOST"]


def test_env_var_default_value(temp_config_with_env):
    """Test environment variable with default value."""
    # Don't set OLLAMA_HOST, should use default
    os.environ["HOME"] = "/tmp/testhome"
    
    loader = ConfigLoader(temp_config_with_env)
    data = loader.load_yaml(temp_config_with_env)
    
    assert data["planner"]["ollama_host"] == "http://localhost:11434"
    
    del os.environ["HOME"]


def test_build_config_from_dict():
    """Test building Config object from dictionary."""
    data = {
        "base_dir": "/tmp/test",
        "planner": {
            "model_name": "custom-model",
            "max_iterations": 5
        },
        "memory": {
            "working_memory_size": 500
        }
    }
    
    loader = ConfigLoader()
    config = loader._build_config(data)
    
    assert config.base_dir == "/tmp/test"
    assert config.planner.model_name == "custom-model"
    assert config.planner.max_iterations == 5
    assert config.memory.working_memory_size == 500


def test_load_config(temp_config_file):
    """Test loading full configuration."""
    reset_config()
    loader = ConfigLoader(temp_config_file)
    config = loader.load()
    
    assert isinstance(config, Config)
    assert config.base_dir == "/tmp/test-agentic-os"
    assert config.planner.model_name == "qwen2.5:7b"
    assert config.scheduler.worker_count == 4
    assert config.logging.level == "INFO"


def test_load_config_defaults():
    """Test loading configuration with defaults when file doesn't exist."""
    reset_config()
    loader = ConfigLoader("/nonexistent/config.yaml")
    config = loader.load()
    
    # Should use defaults
    assert config.base_dir == os.path.expanduser("~/.agentic-os")
    assert config.planner.model_name == "qwen2.5:7b"
    assert config.scheduler.worker_count == 4


def test_get_config_global():
    """Test global config getter."""
    reset_config()
    config = get_config()
    
    assert isinstance(config, Config)
    assert config.planner.model_name == "qwen2.5:7b"


def test_get_config_with_custom_path(temp_config_file):
    """Test global config getter with custom path."""
    reset_config()
    config = get_config(temp_config_file)
    
    assert config.base_dir == "/tmp/test-agentic-os"


def test_config_dataclasses():
    """Test individual config dataclasses."""
    planner = PlannerConfig(
        model_name="test-model",
        temperature=0.5
    )
    assert planner.model_name == "test-model"
    assert planner.temperature == 0.5
    assert planner.max_iterations == 3  # default
    
    memory = MemoryConfig(working_memory_size=2000)
    assert memory.working_memory_size == 2000
    assert memory.faiss_index_dim == 768  # default
    
    scheduler = SchedulerConfig(worker_count=8)
    assert scheduler.worker_count == 8
    assert scheduler.urgent_slice == "urgent.slice"  # default


def test_path_expansion():
    """Test that paths are expanded correctly."""
    config = Config(
        base_dir="~/.agentic-os",
        memory=MemoryConfig(
            episodic_db_path="~/memory/episodic.db"
        )
    )
    
    # Check __post_init__ expands paths
    assert "~" not in config.base_dir
    assert "~" not in config.memory.episodic_db_path


def test_config_reload(temp_config_file):
    """Test reloading configuration."""
    reset_config()
    loader = ConfigLoader(temp_config_file)
    config1 = loader.load()
    
    # Modify the file
    with open(temp_config_file, 'a') as f:
        f.write("\nplanner:\n  model_name: new-model\n")
    
    config2 = loader.reload()
    
    # Should reflect changes
    assert config2.planner.model_name == "new-model"
