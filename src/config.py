import os
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List
import csv


class Config(BaseModel):
    anthropic_api_key: str
    vector_config_path: str = "./vector.toml"
    log_level: str = "INFO"
    llm_model_preference: str = "opus"  # "opus", "sonnet", or "auto"
    type_mappings: Dict[str, Dict[str, str]] = {}
    field_naming_convention: str = "snake_case"  # "snake_case", "camelCase", "PascalCase", "kebab-case", "original"
    
    # Logging configuration
    log_to_file: bool = True
    log_to_console: bool = True
    logs_dir: str = "./logs"
    debug_mode: bool = False
    structured_logging: bool = True
    
    def __init__(self, **data):
        if not data.get("anthropic_api_key"):
            data["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
        
        if not data.get("vector_config_path"):
            data["vector_config_path"] = os.getenv("VECTOR_CONFIG_PATH", "./vector.toml")
            
        if not data.get("log_level"):
            data["log_level"] = os.getenv("LOG_LEVEL", "INFO")
            
        if not data.get("llm_model_preference"):
            data["llm_model_preference"] = os.getenv("LLM_MODEL_PREFERENCE", "opus")
        
        # Load logging configuration from environment
        if "log_to_file" not in data:
            data["log_to_file"] = os.getenv("LOG_TO_FILE", "true").lower() == "true"
        if "log_to_console" not in data:
            data["log_to_console"] = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
        if "logs_dir" not in data:
            data["logs_dir"] = os.getenv("LOGS_DIR", "./logs")
        if "debug_mode" not in data:
            data["debug_mode"] = os.getenv("DEBUG_MODE", "false").lower() == "true"
        if "structured_logging" not in data:
            data["structured_logging"] = os.getenv("STRUCTURED_LOGGING", "true").lower() == "true"
        
        super().__init__(**data)
        self._load_type_mappings()
    
    def _load_type_mappings(self):
        type_maps_file = Path(__file__).parent.parent / "type_maps.csv"
        if type_maps_file.exists():
            with open(type_maps_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('type'):
                        self.type_mappings[row['type']] = row
    
    @property
    def available_types(self) -> List[str]:
        return list(self.type_mappings.keys())
    
    def get_type_info(self, type_name: str) -> Dict[str, str]:
        return self.type_mappings.get(type_name, {})