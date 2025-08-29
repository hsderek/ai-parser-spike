"""
Streaming utilities for memory-efficient file processing
Using dedicated libraries for optimal performance
Following CLAUDE.md performance architecture principles
"""

import regex as re  # Enhanced regex library 
import dask.bag as db
import ijson
from typing import Iterator, List, Callable, Any, Optional, Union, Generator
from pathlib import Path
from concurrent.futures import as_completed, Future
from loguru import logger

from .. import get_thread_pool


def stream_file_lines(file_path: Union[str, Path], 
                     chunk_size: int = 1000,
                     encoding: str = 'utf-8') -> Iterator[str]:
    """
    Stream file lines one at a time (memory efficient)
    
    Args:
        file_path: Path to file
        chunk_size: Buffer size for reading
        encoding: File encoding
        
    Yields:
        Individual lines from file
    """
    with open(file_path, 'r', encoding=encoding, buffering=chunk_size) as f:
        for line in f:
            yield line.rstrip('\n\r')


def stream_file_chunks(file_path: Union[str, Path], 
                      chunk_lines: int = 1000,
                      encoding: str = 'utf-8') -> Iterator[List[str]]:
    """
    Stream file in chunks of lines (memory efficient batch processing)
    
    Args:
        file_path: Path to file
        chunk_lines: Number of lines per chunk
        encoding: File encoding
        
    Yields:
        Lists of lines (chunks)
    """
    chunk = []
    for line in stream_file_lines(file_path, encoding=encoding):
        chunk.append(line)
        if len(chunk) >= chunk_lines:
            yield chunk
            chunk = []
    
    # Yield remaining lines
    if chunk:
        yield chunk


def concurrent_regex_search_dask(file_path: Union[str, Path], 
                               patterns: List[str],
                               chunk_size: int = 1000) -> List[bool]:
    """
    Search multiple regex patterns using Dask for optimal performance
    
    Args:
        file_path: Path to file to search
        patterns: List of regex patterns  
        chunk_size: Lines per chunk for processing
        
    Returns:
        List of boolean results (True if any pattern matched the line)
    """
    # Use Dask bag for parallel line processing
    bag = db.read_text(str(file_path), blocksize="64MB")  # 64MB chunks
    
    def check_patterns(line: str) -> bool:
        """Check if any pattern matches using enhanced regex library"""
        line = line.strip()
        if not line:
            return False
        
        # Use regex library for better performance
        for pattern in patterns:
            if re.search(pattern, line):
                return True
        return False
    
    # Process in parallel using Dask
    results = bag.map(check_patterns).compute()
    return results


def concurrent_regex_search_threadpool(lines: List[str], 
                                     patterns: List[str]) -> List[bool]:
    """
    Search multiple regex patterns across lines using module thread pool
    Smaller datasets - use when lines are already in memory
    """
    # Compile patterns once for performance (regex library)
    compiled_patterns = [re.compile(pattern) for pattern in patterns]
    
    def search_patterns_in_line(line: str) -> bool:
        """Check if any compiled pattern matches the line"""
        line = line.strip()
        if not line:
            return False
            
        for pattern in compiled_patterns:
            if pattern.search(line):
                return True
        return False
    
    executor = get_thread_pool()
    
    # Submit all line checks concurrently
    future_to_index = {}
    for i, line in enumerate(lines):
        future = executor.submit(search_patterns_in_line, line)
        future_to_index[future] = i
    
    # Collect results in order
    results = [False] * len(lines)
    for future in as_completed(future_to_index):
        try:
            index = future_to_index[future]
            results[index] = future.result()
        except Exception as e:
            logger.debug(f"Regex search error on line {future_to_index[future]}: {e}")
    
    return results


def concurrent_line_processor(lines: List[str], 
                            processor_func: Callable[[str], Any],
                            max_workers: Optional[int] = None) -> List[Any]:
    """
    Process lines concurrently using threading
    
    Args:
        lines: List of lines to process
        processor_func: Function to apply to each line
        max_workers: Max threads (uses module default if None)
        
    Returns:
        List of processed results
    """
    executor = get_thread_pool()
    
    # Submit all processing tasks
    future_to_index = {}
    for i, line in enumerate(lines):
        future = executor.submit(processor_func, line)
        future_to_index[future] = i
    
    # Collect results in order
    results = [None] * len(lines)
    for future in as_completed(future_to_index):
        try:
            index = future_to_index[future]
            results[index] = future.result()
        except Exception as e:
            logger.error(f"Processing error on line {future_to_index[future]}: {e}")
            results[index] = None
    
    return results


def stream_and_sample_file(file_path: Union[str, Path], 
                          max_lines: int = 1000,
                          sampling_strategy: str = 'head_and_tail') -> Iterator[str]:
    """
    Stream and intelligently sample large files
    
    Args:
        file_path: Path to file
        max_lines: Maximum lines to yield
        sampling_strategy: 'head', 'head_and_tail', 'distributed'
        
    Yields:
        Sampled lines from file
    """
    if sampling_strategy == 'head':
        # Just take first N lines
        count = 0
        for line in stream_file_lines(file_path):
            if count >= max_lines:
                break
            yield line
            count += 1
            
    elif sampling_strategy == 'head_and_tail':
        # Take first 70% and last 30% of max_lines
        head_count = int(max_lines * 0.7)
        tail_count = max_lines - head_count
        
        # Collect head
        head_lines = []
        line_count = 0
        for line in stream_file_lines(file_path):
            line_count += 1
            if len(head_lines) < head_count:
                head_lines.append(line)
        
        # Yield head
        for line in head_lines:
            yield line
            
        # If file is small enough, we're done
        if line_count <= max_lines:
            return
            
        # For tail, we need to estimate file size or use a circular buffer
        tail_lines = []
        current_pos = len(head_lines)
        
        # Restart and skip to approximate tail position
        skip_ratio = max(1, (line_count - tail_count) // tail_count)
        for i, line in enumerate(stream_file_lines(file_path)):
            if i >= head_count and (i - head_count) % skip_ratio == 0:
                tail_lines.append(line)
                if len(tail_lines) >= tail_count:
                    break
        
        for line in tail_lines:
            yield line
            
    elif sampling_strategy == 'distributed':
        # Distributed sampling across file
        total_lines = sum(1 for _ in stream_file_lines(file_path))  # Count lines first
        if total_lines <= max_lines:
            # File is small, return all
            for line in stream_file_lines(file_path):
                yield line
        else:
            # Sample every Nth line
            step = total_lines // max_lines
            for i, line in enumerate(stream_file_lines(file_path)):
                if i % step == 0:
                    yield line
                    max_lines -= 1
                    if max_lines <= 0:
                        break


def concurrent_file_analysis(file_paths: List[Union[str, Path]], 
                           analyzer_func: Callable[[Path], Any]) -> List[Any]:
    """
    Analyze multiple files concurrently
    
    Args:
        file_paths: List of file paths to analyze
        analyzer_func: Function to apply to each file path
        
    Returns:
        List of analysis results
    """
    executor = get_thread_pool()
    
    future_to_path = {}
    for path in file_paths:
        future = executor.submit(analyzer_func, Path(path))
        future_to_path[future] = path
    
    results = []
    for future in as_completed(future_to_path):
        try:
            result = future.result()
            path = future_to_path[future]
            results.append((path, result))
        except Exception as e:
            path = future_to_path[future]
            logger.error(f"Analysis failed for {path}: {e}")
            results.append((path, None))
    
    return results