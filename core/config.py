"""
Configuration loader for Agentic OS.

Handles loading, validation, and access to YAML configuration files.
Supports environment variable interpolation and default values.
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}')


@dataclass
class PlannerConfig:
    """Configuration for the cognitive planner."""
    model_name: str = "qwen2.5:7b"
    critic_model: str = "qwen2.5:1.5b"
    ollama_host: str = "http://localhost:11434"
    max_iterations: int = 3
    temperature: float = 0.7
    timeout: int = 30


@dataclass
class MemoryConfig:
    """Configuration for memory subsystem."""
    working_memory_size: int = 1000
    episodic_db_path: str = "~/.agentic-os/memory/episodic.db"
    semantic_db_path: str = "~/.agentic-os/memory/semantic.db"
    faiss_index_dim: int = 768
    faiss_index_type: str = "flat"


@dataclass
class SchedulerConfig:
    """Configuration for task scheduler."""
    worker_count: int = 4
    cgroup_path: str = "/sys/fs/cgroup"
    urgent_slice: str = "urgent.slice"
    normal_slice: str = "normal.slice"
    background_slice: str = "background.slice"
    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        "urgency": 1.0,
        "deadline": 0.8,
        "importance": 0.6,
        "cost": 0.4
    })


@dataclass
class VoiceConfig:
    """Configuration for voice subsystem."""
    wake_word_model: str = "hey_jarvis"
    vad_threshold: float = 0.5
    stt_model: str = "base"
    tts_model: str = "en_US-lessac-medium"
    audio_device: Optional[str] = None


@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: str = "INFO"
    format: str = "json"
    log_dir: str = "~/.agentic-os/logs"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5


@dataclass
class Config:
    """
    Main configuration class for Agentic OS.
    
    All configuration values are loaded from YAML files and can be
    overridden by environment variables.
    """
    base_dir: str = "~/.agentic-os"
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    def __post_init__(self):
        """Expand paths after initialization."""
        self.base_dir = os.path.expanduser(self.base_dir)
        self.memory.episodic_db_path = os.path.expanduser(self.memory.episodic_db_path)
        self.memory.semantic_db_path = os.path.expanduser(self.memory.semantic_db_path)
        self.logging.log_dir = os.path.expanduser(self.logging.log_dir)


class ConfigLoader:
    """
    Load and manage configuration from YAML files.
    
    Supports:
    - Loading from default and custom paths
    - Environment variable interpolation (${VAR_NAME})
    - Validation and type checking
    - Merging multiple config files
    """
    
    DEFAULT_CONFIG_PATH = "~/.agentic-os/config.yaml"
    DEFAULT_POLICY_PATH = "~/.agentic-os/policy.yaml"
    DEFAULT_REGISTRY_PATH = "~/.agentic-os/tools/registry.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config loader.
        
        Args:
            config_path: Optional custom path to config file
        """
        self.config_path = os.path.expanduser(
            config_path or self.DEFAULT_CONFIG_PATH
        )
        self._config: Optional[Config] = None
        self._raw_config: Optional[Dict[str, Any]] = None
    
    def _interpolate_env_vars(self, value: Any) -> Any:
        """
        Recursively interpolate environment variables in config values.
        
        Args:
            value: The value to interpolate (can be str, dict, list)
            
        Returns:
            Value with environment variables replaced
        """
        if isinstance(value, str):
            return self._interpolate_env(value)
        elif isinstance(value, dict):
            return {k: self._interpolate_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._interpolate_env_vars(item) for item in value]
        return value
    
    def _interpolate_env(self, text: str) -> str:
        """
        Replace ${VAR} or ${VAR:-default} with env value.
        
        Args:
            text: String to interpolate
            
        Returns:
            String with environment variables replaced
        """
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)
            value = os.environ.get(var_name)
            if value is None:
                return default if default is not None else ""
            return value
        
        return _ENV_PATTERN.sub(replacer, text)
    
    def load_yaml(self, path: str) -> Dict[str, Any]:
        """
        Load a YAML file from disk.
        
        Args:
            path: Path to the YAML file
            
        Returns:
            Parsed YAML as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        
        logger.info("Loading config from %s", path)
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        if data is None:
            data = {}
        
        # Interpolate environment variables
        data = self._interpolate_env_vars(data)
        
        return data
    
    def load(self) -> Config:
        """
        Load the main configuration file.
        
        Returns:
            Config object with all settings
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if self._config is not None:
            return self._config
        
        try:
            self._raw_config = self.load_yaml(self.config_path)
        except FileNotFoundError:
            logger.warning("Config file not found, using defaults")
            self._raw_config = {}
        
        # Build Config object from raw data
        self._config = self._build_config(self._raw_config)
        logger.info("Configuration loaded successfully")
        return self._config
    
    def _build_config(self, data: Dict[str, Any]) -> Config:
        """
        Build Config object from raw dictionary.
        
        Args:
            data: Raw configuration dictionary
            
        Returns:
            Config object
        """
        # Extract nested configs
        planner_data = data.get("planner", {})
        memory_data = data.get("memory", {})
        scheduler_data = data.get("scheduler", {})
        voice_data = data.get("voice", {})
        logging_data = data.get("logging", {})
        
        return Config(
            base_dir=data.get("base_dir", "~/.agentic-os"),
            planner=PlannerConfig(
                model_name=planner_data.get("model_name", "qwen2.5:7b"),
                critic_model=planner_data.get("critic_model", "qwen2.5:1.5b"),
                ollama_host=planner_data.get("ollama_host", "http://localhost:11434"),
                max_iterations=planner_data.get("max_iterations", 3),
                temperature=planner_data.get("temperature", 0.7),
                timeout=planner_data.get("timeout", 30)
            ),
            memory=MemoryConfig(
                working_memory_size=memory_data.get("working_memory_size", 1000),
                episodic_db_path=memory_data.get("episodic_db_path", 
                                                "~/.agentic-os/memory/episodic.db"),
                semantic_db_path=memory_data.get("semantic_db_path",
                                                "~/.agentic-os/memory/semantic.db"),
                faiss_index_dim=memory_data.get("faiss_index_dim", 768),
                faiss_index_type=memory_data.get("faiss_index_type", "flat")
            ),
            scheduler=SchedulerConfig(
                worker_count=scheduler_data.get("worker_count", 4),
                cgroup_path=scheduler_data.get("cgroup_path", "/sys/fs/cgroup"),
                urgent_slice=scheduler_data.get("urgent_slice", "urgent.slice"),
                normal_slice=scheduler_data.get("normal_slice", "normal.slice"),
                background_slice=scheduler_data.get("background_slice", "background.slice"),
                priority_weights=scheduler_data.get("priority_weights", {
                    "urgency": 1.0,
                    "deadline": 0.8,
                    "importance": 0.6,
                    "cost": 0.4
                })
            ),
            voice=VoiceConfig(
                wake_word_model=voice_data.get("wake_word_model", "hey_jarvis"),
                vad_threshold=voice_data.get("vad_threshold", 0.5),
                stt_model=voice_data.get("stt_model", "base"),
                tts_model=voice_data.get("tts_model", "en_US-lessac-medium"),
                audio_device=voice_data.get("audio_device")
            ),
            logging=LoggingConfig(
                level=logging_data.get("level", "INFO"),
                format=logging_data.get("format", "json"),
                log_dir=logging_data.get("log_dir", "~/.agentic-os/logs"),
                max_file_size=logging_data.get("max_file_size", 10485760),
                backup_count=logging_data.get("backup_count", 5)
            )
        )
    
    def load_policy(self) -> Dict[str, Any]:
        """
        Load the policy configuration file.
        
        Returns:
            Policy dictionary
        """
        try:
            return self.load_yaml(self.DEFAULT_POLICY_PATH)
        except FileNotFoundError:
            logger.warning("Policy file not found, using empty policy")
            return {}
    
    def load_registry(self) -> Dict[str, Any]:
        """
        Load the tool registry configuration file.
        
        Returns:
            Registry dictionary
        """
        try:
            return self.load_yaml(self.DEFAULT_REGISTRY_PATH)
        except FileNotFoundError:
            logger.warning("Registry file not found, using empty registry")
            return {}
    
    def reload(self) -> Config:
        """
        Reload configuration from disk.
        
        Returns:
            Updated Config object
        """
        self._config = None
        self._raw_config = None
        return self.load()


# Global config instance
_global_config: Optional[Config] = None
_global_loader: Optional[ConfigLoader] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get the global configuration instance.
    
    Args:
        config_path: Optional custom path to config file
        
    Returns:
        The global Config object
    """
    global _global_config, _global_loader
    
    if _global_config is None or config_path is not None:
        _global_loader = ConfigLoader(config_path)
        _global_config = _global_loader.load()
    
    return _global_config


def get_config_loader() -> ConfigLoader:
    """
    Get the global config loader instance.
    
    Returns:
        The global ConfigLoader object
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = ConfigLoader()
    return _global_loader


def reset_config() -> None:
    """Reset global config (mainly for testing)."""
    global _global_config, _global_loader
    _global_config = None
    _global_loader = None
