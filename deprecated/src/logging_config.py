#!/usr/bin/env python3
"""
Configurable logging setup using loguru
Supports file output to ./logs directory and console output
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
import json


class LoggingConfig:
    """
    Centralized logging configuration for the AI parser project
    """
    
    def __init__(
        self, 
        log_level: str = "INFO",
        log_to_file: bool = True,
        log_to_console: bool = True,
        logs_dir: str = "./logs",
        app_name: str = "ai_parser",
        structured_logging: bool = True,
        debug_mode: bool = False
    ):
        self.log_level = log_level.upper()
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.logs_dir = Path(logs_dir)
        self.app_name = app_name
        self.structured_logging = structured_logging
        self.debug_mode = debug_mode
        
        # Ensure logs directory exists
        if self.log_to_file:
            self.logs_dir.mkdir(exist_ok=True)
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure loguru logging"""
        
        # Remove default handler
        logger.remove()
        
        # Console logging
        if self.log_to_console:
            console_format = self._get_console_format()
            logger.add(
                sys.stdout,
                level=self.log_level,
                format=console_format,
                colorize=True,
                backtrace=self.debug_mode,
                diagnose=self.debug_mode
            )
        
        # File logging
        if self.log_to_file:
            self._setup_file_logging()
        
        # Add context for structured logging
        if self.structured_logging:
            self._setup_structured_context()
    
    def _get_console_format(self) -> str:
        """Get console logging format"""
        if self.debug_mode:
            return (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        else:
            return (
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<level>{message}</level>"
            )
    
    def _setup_file_logging(self):
        """Setup file-based logging"""
        
        # Main application log
        main_log = self.logs_dir / f"{self.app_name}.log"
        logger.add(
            main_log,
            level=self.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="7 days",
            compression="gz",
            backtrace=True,
            diagnose=self.debug_mode
        )
        
        # Error log (only errors and above)
        error_log = self.logs_dir / f"{self.app_name}_errors.log"
        logger.add(
            error_log,
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {exception}",
            rotation="5 MB",
            retention="30 days",
            compression="gz",
            backtrace=True,
            diagnose=True
        )
        
        # Performance/metrics log (structured JSON)
        if self.structured_logging:
            metrics_log = self.logs_dir / f"{self.app_name}_metrics.jsonl"
            logger.add(
                metrics_log,
                level="INFO",
                format="{message}",
                rotation="50 MB",
                retention="14 days",
                filter=lambda record: "metrics" in record["extra"]
            )
    
    def _setup_structured_context(self):
        """Setup structured logging context"""
        logger.configure(
            extra={
                "app_name": self.app_name,
                "version": "1.0.0",
                "environment": "development"
            }
        )
    
    def get_logger(self, name: str = None) -> "logger":
        """Get a logger instance with optional name binding"""
        if name:
            return logger.bind(component=name)
        return logger
    
    def log_metrics(self, component: str, metrics: Dict[str, Any]):
        """Log structured metrics data"""
        from datetime import datetime
        logger.bind(metrics=True, component=component).info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "metrics": metrics
        }))
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics"""
        self.log_metrics("performance", {
            "operation": operation,
            "duration_ms": duration_ms,
            **kwargs
        })
    
    def log_llm_usage(self, model: str, tokens: int, cost: float, operation: str):
        """Log LLM usage metrics"""
        self.log_metrics("llm_usage", {
            "model": model,
            "tokens": tokens,
            "cost_usd": cost,
            "operation": operation
        })
    
    def log_parsing_result(
        self, 
        source_file: str, 
        fields_extracted: int, 
        records_processed: int,
        success: bool,
        duration_ms: float
    ):
        """Log parsing operation results"""
        self.log_metrics("parsing", {
            "source_file": source_file,
            "fields_extracted": fields_extracted,
            "records_processed": records_processed,
            "success": success,
            "duration_ms": duration_ms
        })


# Global logging instance
_logging_config: Optional[LoggingConfig] = None


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    logs_dir: str = "./logs",
    app_name: str = "ai_parser",
    structured_logging: bool = True,
    debug_mode: bool = False
) -> LoggingConfig:
    """
    Setup global logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Enable file logging
        log_to_console: Enable console logging
        logs_dir: Directory for log files
        app_name: Application name for log files
        structured_logging: Enable structured/metrics logging
        debug_mode: Enable debug features (backtraces, etc.)
        
    Returns:
        LoggingConfig instance
    """
    global _logging_config
    _logging_config = LoggingConfig(
        log_level=log_level,
        log_to_file=log_to_file,
        log_to_console=log_to_console,
        logs_dir=logs_dir,
        app_name=app_name,
        structured_logging=structured_logging,
        debug_mode=debug_mode
    )
    return _logging_config


def get_logger(name: str = None) -> "logger":
    """
    Get logger instance with optional component name
    
    Args:
        name: Component name for logging context
        
    Returns:
        Configured logger instance
    """
    if _logging_config is None:
        # Use default configuration if not setup
        setup_logging()
    
    return _logging_config.get_logger(name)


def log_metrics(component: str, metrics: Dict[str, Any]):
    """Log structured metrics"""
    if _logging_config:
        _logging_config.log_metrics(component, metrics)


def log_performance(operation: str, duration_ms: float, **kwargs):
    """Log performance metrics"""
    if _logging_config:
        _logging_config.log_performance(operation, duration_ms, **kwargs)


def log_llm_usage(model: str, tokens: int, cost: float, operation: str):
    """Log LLM usage metrics"""
    if _logging_config:
        _logging_config.log_llm_usage(model, tokens, cost, operation)


def log_parsing_result(
    source_file: str, 
    fields_extracted: int, 
    records_processed: int,
    success: bool,
    duration_ms: float
):
    """Log parsing operation results"""
    if _logging_config:
        _logging_config.log_parsing_result(
            source_file, fields_extracted, records_processed, success, duration_ms
        )