"""
Configuration loader with auto-sensing and smart defaults
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from loguru import logger


class DFEConfigLoader:
    """Smart configuration loader"""
    
    @classmethod
    def load(cls, config_path: str = None) -> Dict[str, Any]:
        """
        Load configuration with auto-sensing
        
        Args:
            config_path: Optional path to config file
            
        Returns:
            Configuration dictionary
        """
        config = {}
        
        # Try multiple config locations
        search_paths = cls._get_config_search_paths(config_path)
        
        for path in search_paths:
            if path.exists():
                logger.info(f"Loading config from: {path}")
                with open(path, 'r') as f:
                    config = yaml.safe_load(f)
                break
        else:
            logger.warning("No config file found, using defaults")
            config = cls._get_default_config()
        
        # Apply environment overrides
        config = cls._apply_env_overrides(config)
        
        # Apply smart defaults
        config = cls._apply_smart_defaults(config)
        
        return config
    
    @classmethod
    def _get_config_search_paths(cls, config_path: str = None) -> list:
        """Get list of paths to search for config"""
        paths = []
        
        if config_path:
            paths.append(Path(config_path))
        
        # Search in standard locations
        # __file__ = .../src/dfe_ai_parser_vrl/config/loader.py
        # parent = .../src/dfe_ai_parser_vrl/config/  
        # parent.parent = .../src/dfe_ai_parser_vrl/
        # parent.parent.parent = .../src/
        # parent.parent.parent.parent = .../  (project root)
        project_root = Path(__file__).parent.parent.parent.parent
        
        paths.extend([
            project_root / "config" / "config.yaml",  # /projects/ai-parser-spike/config/config.yaml
            project_root / "config.yaml", 
            Path.home() / ".vrl_parser" / "config.yaml",
            Path("/etc/vrl_parser/config.yaml"),
        ])
        
        return paths
    
    @classmethod
    def _get_default_config(cls) -> Dict[str, Any]:
        """Get minimal default configuration"""
        return {
            "defaults": {
                "platform": "anthropic",
                "capability": "reasoning",
                "max_iterations": 10,
                "validation_enabled": True,
                "streaming": True
            },
            "platform_patterns": {
                "anthropic": ["claude"],
                "openai": ["gpt", "o[0-9]"],
                "google": ["gemini"]
            },
            "platforms": {
                "anthropic": {
                    "capabilities": {
                        "reasoning": {"families": ["opus", "sonnet"]},
                        "balanced": {"families": ["sonnet", "haiku"]},
                        "efficient": {"families": ["haiku"]}
                    }
                }
            },
            "vrl_generation": {
                "max_iterations": 10,
                "iteration_delay": 2,
                "validation": {
                    "pyvrl_enabled": True,
                    "vector_cli_enabled": True,
                    "timeout": 30
                },
                "error_fixing": {
                    "enabled": True,
                    "max_fix_attempts": 3
                }
            },
            "paths": {
                "samples": "samples/",
                "output": "samples-parsed/",
                "logs": "logs/",
                "sessions": ".tmp/llm_sessions/",
                "deprecated": "deprecated/"
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
    
    @classmethod
    def _apply_env_overrides(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        
        # API keys (don't store in config)
        # These are handled directly by LiteLLM from environment
        
        # Override platform preference
        if os.getenv("VRL_PLATFORM"):
            config.setdefault("defaults", {})["platform"] = os.getenv("VRL_PLATFORM")
        
        # Override capability preference
        if os.getenv("VRL_CAPABILITY"):
            config.setdefault("defaults", {})["capability"] = os.getenv("VRL_CAPABILITY")
        
        # Override max iterations
        if os.getenv("VRL_MAX_ITERATIONS"):
            config.setdefault("vrl_generation", {})["max_iterations"] = int(os.getenv("VRL_MAX_ITERATIONS"))
        
        # Override validation settings
        if os.getenv("VRL_SKIP_VALIDATION"):
            config.setdefault("defaults", {})["validation_enabled"] = False
        
        # Override logging level
        if os.getenv("VRL_LOG_LEVEL"):
            config.setdefault("logging", {})["level"] = os.getenv("VRL_LOG_LEVEL")
        
        return config
    
    @classmethod
    def _apply_smart_defaults(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply smart defaults based on auto-sensing"""
        
        # Auto-detect if we have API keys
        if os.getenv("ANTHROPIC_API_KEY"):
            if not config.get("defaults", {}).get("platform"):
                config.setdefault("defaults", {})["platform"] = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            if not config.get("defaults", {}).get("platform"):
                config.setdefault("defaults", {})["platform"] = "openai"
        elif os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
            if not config.get("defaults", {}).get("platform"):
                config.setdefault("defaults", {})["platform"] = "google"
        
        # Auto-detect if Vector CLI is installed
        import subprocess
        try:
            subprocess.run(["vector", "--version"], capture_output=True, check=True)
            logger.debug("Vector CLI detected")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug("Vector CLI not found, disabling Vector validation")
            config.setdefault("vrl_generation", {}).setdefault("validation", {})["vector_cli_enabled"] = False
        
        # Auto-detect if PyVRL is installed
        try:
            import pyvrl
            logger.debug("PyVRL detected")
        except ImportError:
            logger.debug("PyVRL not found, disabling PyVRL validation")
            config.setdefault("vrl_generation", {}).setdefault("validation", {})["pyvrl_enabled"] = False
        
        # Ensure all paths exist
        paths_config = config.get("paths", {})
        for path_key, path_value in paths_config.items():
            path = Path(path_value)
            if not path.exists() and path_key != "deprecated":
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {path}")
        
        return config