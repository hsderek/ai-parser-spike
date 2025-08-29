"""
Example of how to use the module-wide threading configuration
"""

import time
from concurrent.futures import as_completed
from typing import List, Any
from loguru import logger

# Import the module-level threading functions
from .. import get_thread_pool, get_max_threads


def process_items_concurrently(items: List[Any], processor_func) -> List[Any]:
    """
    Example function showing how to use the module's thread pool
    for concurrent processing of items
    """
    logger.info(f"Processing {len(items)} items using {get_max_threads()} threads")
    
    # Get the shared thread pool
    executor = get_thread_pool()
    
    # Submit all tasks
    future_to_item = {
        executor.submit(processor_func, item): item 
        for item in items
    }
    
    results = []
    for future in as_completed(future_to_item):
        try:
            result = future.result()
            results.append(result)
        except Exception as e:
            item = future_to_item[future]
            logger.error(f"Failed to process item {item}: {e}")
            results.append(None)
    
    return results


def example_processor(item: Any) -> Any:
    """Example processing function that simulates work"""
    time.sleep(0.1)  # Simulate processing time
    return f"processed_{item}"


def demo_threading():
    """Demonstrate the threading configuration"""
    print(f"=== DFE Threading Demo ===")
    print(f"Max threads configured: {get_max_threads()}")
    
    # Process some items concurrently
    test_items = list(range(20))
    start_time = time.time()
    
    results = process_items_concurrently(test_items, example_processor)
    
    end_time = time.time()
    print(f"Processed {len(results)} items in {end_time - start_time:.2f} seconds")
    print(f"Results sample: {results[:5]}")


if __name__ == "__main__":
    demo_threading()