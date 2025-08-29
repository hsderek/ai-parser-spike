"""
Vector Daemon Manager for Efficient VRL Testing

Manages a persistent Vector instance with hot-reload capabilities
to eliminate startup overhead during performance iteration testing.
"""

import os
import time
import json
import socket
import subprocess
import tempfile
import yaml
import requests
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from loguru import logger
from jinja2 import Environment, FileSystemLoader


class VectorDaemon:
    """Persistent Vector instance for efficient VRL testing"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.api_port: Optional[int] = None
        self.temp_dir: Optional[Path] = None
        self.base_config: Dict[str, Any] = {}
        self.is_running = False
        
        # Setup Jinja2 environment for Vector config templates
        template_dir = Path(__file__).parent
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
    def start(self) -> bool:
        """Start Vector daemon with base configuration"""
        try:
            # Create persistent temp directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix="vector_daemon_"))
            data_dir = self.temp_dir / "vector_data"
            data_dir.mkdir(exist_ok=True)
            
            # Find available port
            self.api_port = self._find_available_port()
            
            # Base Vector configuration
            self.base_config = {
                'data_dir': str(data_dir),
                'api': {
                    'enabled': True,
                    'address': f'127.0.0.1:{self.api_port}',
                    'graphql': True,
                    'playground': False  # Disable playground for performance
                },
                'sources': {},
                'transforms': {},
                'sinks': {}
            }
            
            config_file = self.temp_dir / "vector_daemon.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(self.base_config, f)
            
            # Start Vector process with config watching enabled
            env = os.environ.copy()
            env['VECTOR_DATA_DIR'] = str(data_dir)
            env['VECTOR_WATCH_CONFIG_METHOD'] = 'recommended'  # Event-based file watching
            
            self.process = subprocess.Popen(
                ['vector', 
                 '--config', str(config_file),
                 '--watch-config-method', 'recommended',  # Watch for config file changes
                 '--threads', '1'  # Single thread for predictable performance
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for API to be ready
            if self._wait_for_api():
                self.is_running = True
                logger.info(f"✅ Vector daemon started on port {self.api_port}")
                return True
            else:
                logger.error("❌ Vector daemon failed to start")
                self.stop()
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Vector daemon: {e}")
            self.stop()
            return False
    
    def test_vrl(self, vrl_code: str, sample_data: str, test_name: str = "test") -> Tuple[int, List[Dict], float]:
        """
        Test VRL code using the running daemon
        
        Args:
            vrl_code: VRL code to test
            sample_data: Sample log data
            test_name: Unique test identifier
            
        Returns:
            Tuple of (events_processed, output_events, duration_seconds)
        """
        if not self.is_running:
            raise RuntimeError("Vector daemon not running")
        
        start_time = time.time()
        
        try:
            # Create test-specific files
            input_file = self.temp_dir / f"{test_name}_input.json"
            output_file = self.temp_dir / f"{test_name}_output.json"
            
            # Write sample data
            sample_lines = sample_data.strip().split('\n')
            with open(input_file, 'w') as f:
                for line in sample_lines:
                    if line.strip():
                        if line.startswith('{'):
                            f.write(line + '\n')
                        else:
                            f.write(json.dumps({"message": line}) + '\n')
            
            # Hot-reload Vector config for this test
            test_config = self._build_test_config(vrl_code, str(input_file), str(output_file), test_name)
            
            success = self._reload_vector_config(test_config)
            if not success:
                return 0, [], time.time() - start_time
            
            # Monitor processing via GraphQL
            events_processed = self._monitor_processing(test_name, len(sample_lines))
            
            # Read output events
            output_events = []
            if output_file.exists():
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                output_events.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            
            duration = time.time() - start_time
            logger.debug(f"VRL test complete: {events_processed} events in {duration:.2f}s")
            
            return events_processed, output_events, duration
            
        except Exception as e:
            logger.error(f"VRL test failed: {e}")
            return 0, [], time.time() - start_time
    
    def _build_test_config(self, vrl_code: str, input_file: str, output_file: str, test_name: str) -> str:
        """Build Vector config for specific VRL test using Jinja template"""
        try:
            template = self.jinja_env.get_template('vector_config.j2')
            
            config_yaml = template.render(
                data_dir=str(self.temp_dir / "vector_data"),
                api_port=self.api_port,
                test_name=test_name,
                input_file=input_file,
                output_file=output_file,
                vrl_code=vrl_code
            )
            
            return config_yaml
            
        except Exception as e:
            logger.error(f"Failed to build Vector config from template: {e}")
            # Fallback to basic config
            return f"""
data_dir: {self.temp_dir}/vector_data

api:
  enabled: true
  address: "127.0.0.1:{self.api_port}"
  graphql: true

sources:
  {test_name}_source:
    type: file
    include: ["{input_file}"]
    read_from: beginning

transforms:
  {test_name}_vrl:
    type: remap
    inputs: ["{test_name}_source"]  
    source: |
{vrl_code}

sinks:
  {test_name}_output:
    type: file
    inputs: ["{test_name}_vrl"]
    path: "{output_file}"
    encoding:
      codec: json
"""
    
    def _reload_vector_config(self, new_config_yaml: str) -> bool:
        """Hot-reload Vector configuration by updating config file (Vector watches for changes)"""
        try:
            config_file = self.temp_dir / "vector_daemon.yaml"
            
            # Update config file - Vector will detect the change automatically
            with open(config_file, 'w') as f:
                f.write(new_config_yaml)
            
            logger.debug(f"Updated Vector config file, waiting for hot-reload...")
            
            # Give Vector time to reload the configuration
            time.sleep(2)
            
            # Verify reload by checking if new components are active via GraphQL
            return self._verify_config_reload(new_config)
            
        except Exception as e:
            logger.error(f"Config reload failed: {e}")
            return False
    
    def _verify_config_reload(self, expected_config: Dict[str, Any]) -> bool:
        """Verify that Vector reloaded the configuration by checking component names"""
        api_url = f"http://127.0.0.1:{self.api_port}/graphql"
        
        # Query for current component configuration
        components_query = """
        query {
            components {
                sources {
                    name
                }
                transforms {
                    name
                }
                sinks {
                    name
                }
            }
        }
        """
        
        try:
            response = requests.post(
                api_url,
                json={'query': components_query},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data and 'data' in data:
                    components = data['data'].get('components', {})
                    
                    # Check if expected sources/transforms/sinks are present
                    current_sources = [s['name'] for s in components.get('sources', [])]
                    current_transforms = [t['name'] for t in components.get('transforms', [])]
                    current_sinks = [s['name'] for s in components.get('sinks', [])]
                    
                    expected_sources = list(expected_config.get('sources', {}).keys())
                    expected_transforms = list(expected_config.get('transforms', {}).keys())
                    expected_sinks = list(expected_config.get('sinks', {}).keys())
                    
                    # Check if all expected components are active
                    sources_ok = all(source in current_sources for source in expected_sources)
                    transforms_ok = all(transform in current_transforms for transform in expected_transforms)
                    sinks_ok = all(sink in current_sinks for sink in expected_sinks)
                    
                    if sources_ok and transforms_ok and sinks_ok:
                        logger.debug("✅ Config reload verified - all components active")
                        return True
                    else:
                        logger.warning(f"⚠️ Config reload partial: sources={sources_ok}, transforms={transforms_ok}, sinks={sinks_ok}")
                        return False
            
            return False
            
        except Exception as e:
            logger.warning(f"Config reload verification failed: {e}")
            return False
    
    def _monitor_processing(self, test_name: str, expected_events: int, max_wait: int = 30) -> int:
        """Monitor test processing via GraphQL API"""
        api_url = f"http://127.0.0.1:{self.api_port}/graphql"
        
        metrics_query = f"""
        query {{
            components {{
                sinks {{
                    name
                    metrics {{
                        received {{
                            events {{
                                total
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        events_processed = 0
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = requests.post(
                    api_url,
                    json={'query': metrics_query},
                    timeout=2
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data and 'data' in data:
                        sinks = data['data'].get('components', {}).get('sinks', [])
                        
                        for sink in sinks:
                            if sink.get('name') == f'{test_name}_output':
                                received = sink.get('metrics', {}).get('received', {})
                                events = received.get('events', {})
                                total = events.get('total', 0)
                                
                                if total != events_processed:
                                    events_processed = total
                                    logger.debug(f"Daemon test: {events_processed}/{expected_events} events")
                                
                                if events_processed >= expected_events:
                                    return events_processed
                
                time.sleep(0.2)
                
            except Exception as e:
                logger.debug(f"Daemon monitoring error: {e}")
                time.sleep(0.5)
                continue
        
        return events_processed
    
    def _wait_for_api(self, timeout: int = 10) -> bool:
        """Wait for Vector GraphQL API to be ready"""
        api_url = f"http://127.0.0.1:{self.api_port}/graphql"
        
        for _ in range(timeout * 2):  # Check every 0.5s
            try:
                response = requests.post(
                    api_url,
                    json={'query': '{ uptime }'},
                    timeout=1
                )
                if response.status_code == 200:
                    return True
            except:
                pass
            
            time.sleep(0.5)
        
        return False
    
    def _find_available_port(self, start_port: int = 9000) -> int:
        """Find available port for daemon API"""
        for port in range(start_port, start_port + 1000):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result != 0:
                        return port
            except:
                continue
        
        import random
        return random.randint(12000, 13000)
    
    def stop(self):
        """Stop Vector daemon and cleanup"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
        
        self.is_running = False
        logger.info("Vector daemon stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Global daemon instance for reuse across tests  
_vector_daemon: Optional[VectorDaemon] = None

def get_vector_daemon() -> VectorDaemon:
    """Get or create global Vector daemon instance"""
    global _vector_daemon
    
    if _vector_daemon is None or not _vector_daemon.is_running:
        _vector_daemon = VectorDaemon()
        _vector_daemon.start()
    
    return _vector_daemon

def stop_vector_daemon():
    """Stop global Vector daemon"""
    global _vector_daemon
    if _vector_daemon:
        _vector_daemon.stop()
        _vector_daemon = None