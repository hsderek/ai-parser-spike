"""
DFE AI Parser VRL - AI-powered Vector Remap Language generator for HyperSec Data Fusion Engine
"""

import os
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

__version__ = "0.1.0"
__author__ = "HyperSec DFE Team"

# Module-wide threading configuration
class DFEThreadingConfig:
    """Module-wide threading configuration for DFE AI Parser VRL"""
    
    def __init__(self):
        self._max_workers = self._detect_optimal_thread_count()
        self._thread_pool = None
        
    def _detect_optimal_thread_count(self) -> int:
        """Detect optimal thread count based on CPU cores and config overrides"""
        # Check for environment variable override first
        config_threads = os.getenv('DFE_MAX_THREADS')
        if config_threads:
            try:
                override_count = int(config_threads)
                logger.info(f"Using environment override: {override_count} threads")
                return max(1, override_count)
            except ValueError:
                logger.warning(f"Invalid DFE_MAX_THREADS value: {config_threads}, using auto-detection")
        
        # Load threading config from config file
        try:
            from .config.loader import DFEConfigLoader
            config = DFEConfigLoader.load()
            threading_config = config.get('threading', {})
            
            # Check if auto-detection is disabled
            if not threading_config.get('auto_detect_cores', True):
                logger.info("CPU auto-detection disabled in config")
                return threading_config.get('min_threads', 2)
                
        except Exception as e:
            logger.debug(f"Could not load config for threading: {e}")
            threading_config = {}
        
        # Auto-detect based on CPU cores
        try:
            cpu_count = os.cpu_count() or 1
            
            # Get config values with defaults (container optimized)
            core_utilization = threading_config.get('core_utilization', 1.0)  # 100% for containers
            max_limit = threading_config.get('max_threads_limit', 32)  # Higher limit for containers
            min_threads = threading_config.get('min_threads', 1)
            
            # Calculate optimal threads
            optimal_threads = max(min_threads, min(max_limit, int(cpu_count * core_utilization)))
            logger.info(f"Detected {cpu_count} CPU cores, using {optimal_threads} threads ({core_utilization:.0%} utilization)")
            return optimal_threads
            
        except Exception as e:
            logger.warning(f"Failed to detect CPU cores: {e}, defaulting to 2 threads")
            return 2
    
    @property
    def max_workers(self) -> int:
        """Get the configured maximum worker threads"""
        return self._max_workers
        
    def set_max_workers(self, count: int):
        """Override the maximum worker threads"""
        if count < 1:
            raise ValueError("Thread count must be at least 1")
        self._max_workers = count
        # Reset thread pool to apply new setting
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
        logger.info(f"Thread count set to {count}")
    
    def get_thread_pool(self) -> ThreadPoolExecutor:
        """Get a shared thread pool executor"""
        if self._thread_pool is None or self._thread_pool._shutdown:
            self._thread_pool = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="dfe-vrl"
            )
        return self._thread_pool
    
    def shutdown(self):
        """Shutdown the thread pool"""
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None

# Global threading configuration instance
_threading_config = DFEThreadingConfig()

# Public API for threading configuration
def get_max_threads() -> int:
    """Get the maximum number of threads configured for the module"""
    return _threading_config.max_workers

def set_max_threads(count: int):
    """Set the maximum number of threads for the module"""
    _threading_config.set_max_workers(count)

def get_thread_pool() -> ThreadPoolExecutor:
    """Get a shared thread pool executor for async operations"""
    return _threading_config.get_thread_pool()

# Module imports
from .core.generator import DFEVRLGenerator  # baseline_stage
from .core.performance import DFEVRLPerformanceOptimizer, VRLPerformanceOptimizer  # performance_stage
from .llm.client import DFELLMClient
from .config.loader import DFEConfigLoader

__all__ = [
    "DFEVRLGenerator",  # baseline_stage: Establishes working baseline VRL
    "DFEVRLPerformanceOptimizer",  # performance_stage: Optimizes candidate_baseline 
    "VRLPerformanceOptimizer", 
    "DFELLMClient", "DFEConfigLoader",
    "get_max_threads", "set_max_threads", "get_thread_pool"
]