#!/usr/bin/env python3
"""
Generate Large Diverse Sample Logs

Creates comprehensive test data covering multiple log formats and use cases.
Generates samples in the single-line syslog JSON schema.
"""

import json
import random
import datetime
import ipaddress
import uuid
from typing import List, Dict, Any

class DiverseLogGenerator:
    """Generate diverse log samples for comprehensive testing"""
    
    def __init__(self):
        self.start_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        self.ips = ['10.0.0.1', '192.168.1.100', '172.16.50.10', '203.0.113.45', '198.51.100.22']
        self.users = ['admin', 'jsmith', 'alice', 'bob', 'service-account', 'root', 'webapp']
        self.actions = ['allow', 'deny', 'drop', 'accept', 'reject']
        self.protocols = ['TCP', 'UDP', 'ICMP', 'HTTP', 'HTTPS', 'SSH', 'DNS']
        
    def generate_timestamp(self) -> str:
        """Generate incrementing timestamp"""
        self.start_time += datetime.timedelta(seconds=random.randint(1, 60))
        return self.start_time.isoformat()
    
    def random_ip(self) -> str:
        """Generate random IP address"""
        return f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
    
    def generate_aws_cloudtrail(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate AWS CloudTrail logs"""
        samples = []
        events = ['CreateBucket', 'DeleteBucket', 'PutObject', 'GetObject', 'AssumeRole', 'CreateUser', 'DeleteUser']
        
        for _ in range(count):
            event = {
                "message": json.dumps({
                    "eventTime": self.generate_timestamp(),
                    "eventName": random.choice(events),
                    "awsRegion": random.choice(['us-east-1', 'eu-west-1', 'ap-southeast-1']),
                    "sourceIPAddress": self.random_ip(),
                    "userIdentity": {
                        "type": random.choice(["IAMUser", "AssumedRole", "Root"]),
                        "principalId": f"AIDA{uuid.uuid4().hex[:10].upper()}",
                        "userName": random.choice(self.users)
                    },
                    "eventSource": "s3.amazonaws.com",
                    "requestParameters": {
                        "bucketName": f"bucket-{random.randint(1000,9999)}"
                    }
                }),
                "source": "aws-cloudtrail",
                "timestamp": self.generate_timestamp()
            }
            samples.append(event)
        return samples
    
    def generate_windows_security(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate Windows Security Event logs"""
        samples = []
        event_ids = [4624, 4625, 4634, 4672, 4720, 4726, 4732, 4735]  # Login, failed login, logoff, etc.
        
        for _ in range(count):
            event_id = random.choice(event_ids)
            msg = f"EventID={event_id} "
            
            if event_id == 4624:
                msg += f"An account was successfully logged on. Subject: {random.choice(self.users)} "
            elif event_id == 4625:
                msg += f"An account failed to log on. Subject: {random.choice(self.users)} "
            
            msg += f"LogonType={random.randint(2,11)} "
            msg += f"WorkstationName=DESKTOP-{random.randint(100,999)} "
            msg += f"IpAddress={self.random_ip()}"
            
            samples.append({
                "message": msg,
                "source": "windows-security",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_zeek_ids(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate Zeek/Bro IDS logs"""
        samples = []
        
        for _ in range(count):
            conn_state = random.choice(['SF', 'S0', 'S1', 'REJ', 'RSTO'])
            samples.append({
                "message": f"{self.generate_timestamp()} "
                          f"uid=C{uuid.uuid4().hex[:8]} "
                          f"id.orig_h={self.random_ip()} "
                          f"id.orig_p={random.randint(1024,65535)} "
                          f"id.resp_h={self.random_ip()} "
                          f"id.resp_p={random.choice([80,443,22,21,25,53])} "
                          f"proto={random.choice(['tcp','udp'])} "
                          f"conn_state={conn_state} "
                          f"duration={random.uniform(0.001, 300):.3f} "
                          f"orig_bytes={random.randint(0, 1000000)} "
                          f"resp_bytes={random.randint(0, 1000000)}",
                "source": "zeek-ids",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_kubernetes(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate Kubernetes logs"""
        samples = []
        namespaces = ['default', 'kube-system', 'production', 'staging']
        resources = ['pod', 'deployment', 'service', 'ingress', 'configmap']
        verbs = ['create', 'update', 'patch', 'delete', 'get', 'list', 'watch']
        
        for _ in range(count):
            samples.append({
                "message": json.dumps({
                    "kind": "Event",
                    "apiVersion": "audit.k8s.io/v1",
                    "level": random.choice(["Metadata", "Request", "RequestResponse"]),
                    "timestamp": self.generate_timestamp(),
                    "user": {"username": random.choice(self.users)},
                    "verb": random.choice(verbs),
                    "objectRef": {
                        "resource": random.choice(resources),
                        "namespace": random.choice(namespaces),
                        "name": f"{random.choice(resources)}-{uuid.uuid4().hex[:8]}"
                    },
                    "sourceIPs": [self.random_ip()],
                    "responseStatus": {"code": random.choice([200, 201, 403, 404, 500])}
                }),
                "source": "kubernetes-audit",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_vpc_flow_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate AWS VPC Flow Logs"""
        samples = []
        
        for _ in range(count):
            action = random.choice(['ACCEPT', 'REJECT'])
            samples.append({
                "message": f"2 {random.randint(100000,999999)} eni-{uuid.uuid4().hex[:8]} "
                          f"{self.random_ip()} {self.random_ip()} "
                          f"{random.randint(1024,65535)} {random.randint(1,65535)} "
                          f"{random.choice([6,17,1])} "  # TCP, UDP, ICMP
                          f"{random.randint(1,1000)} {random.randint(100,1000000)} "
                          f"{int(self.start_time.timestamp())} {int((self.start_time + datetime.timedelta(seconds=60)).timestamp())} "
                          f"{action} OK",
                "source": "aws-vpcflow",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_apache_combined(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate Apache combined format logs"""
        samples = []
        paths = ['/index.html', '/api/users', '/login', '/admin', '/static/css/main.css', '/favicon.ico']
        status_codes = [200, 201, 301, 302, 400, 401, 403, 404, 500, 503]
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'curl/7.68.0',
            'python-requests/2.28.0'
        ]
        
        for _ in range(count):
            samples.append({
                "message": f'{self.random_ip()} - {random.choice(self.users + ["-"])} '
                          f'[{self.start_time.strftime("%d/%b/%Y:%H:%M:%S +0000")}] '
                          f'"GET {random.choice(paths)} HTTP/1.1" '
                          f'{random.choice(status_codes)} {random.randint(100, 50000)} '
                          f'"http://example.com/" "{random.choice(user_agents)}"',
                "source": "apache-combined",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_linux_auditd(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate Linux auditd logs"""
        samples = []
        syscalls = ['open', 'execve', 'connect', 'bind', 'chmod', 'chown', 'unlink']
        
        for _ in range(count):
            samples.append({
                "message": f'type=SYSCALL msg=audit({int(self.start_time.timestamp())}.{random.randint(100,999)}:{random.randint(10000,99999)}): '
                          f'arch=c000003e syscall={random.randint(0,300)} success={random.choice(["yes","no"])} '
                          f'exit={random.choice([0,-1,-13])} a0=7fff5e4f8c50 a1=0 a2=0 a3=0 items=1 '
                          f'ppid={random.randint(1,10000)} pid={random.randint(1,10000)} '
                          f'auid={random.randint(0,1000)} uid={random.randint(0,1000)} gid={random.randint(0,1000)} '
                          f'comm="{random.choice(syscalls)}" exe="/usr/bin/{random.choice(syscalls)}"',
                "source": "linux-auditd",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_cef_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate CEF (Common Event Format) logs"""
        samples = []
        vendors = ['Fortinet', 'CheckPoint', 'Symantec', 'McAfee']
        
        for _ in range(count):
            severity = random.randint(0, 10)
            samples.append({
                "message": f'CEF:0|{random.choice(vendors)}|{random.choice(vendors)}Device|1.0|'
                          f'{random.randint(100,999)}|{random.choice(["Intrusion Detected","Malware Found","Policy Violation"])}|'
                          f'{severity}|src={self.random_ip()} dst={self.random_ip()} '
                          f'spt={random.randint(1024,65535)} dpt={random.randint(1,65535)} '
                          f'proto={random.choice(self.protocols)} act={random.choice(self.actions)} '
                          f'cat={random.choice(["Network","Security","System"])} '
                          f'deviceProcessName={random.choice(["firewall","ids","antivirus"])}',
                "source": "cef",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_json_structured(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate JSON structured application logs"""
        samples = []
        levels = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
        components = ['api', 'database', 'cache', 'queue', 'auth', 'payment']
        
        for _ in range(count):
            level = random.choice(levels)
            log_data = {
                "timestamp": self.generate_timestamp(),
                "level": level,
                "component": random.choice(components),
                "thread": f"thread-{random.randint(1,20)}",
                "user_id": random.choice([None] + [f"user_{i}" for i in range(100)]),
                "request_id": str(uuid.uuid4()),
                "message": f"Processing request for {random.choice(components)}",
                "metrics": {
                    "duration_ms": random.randint(1, 5000),
                    "memory_mb": random.randint(10, 500)
                }
            }
            
            if level == 'ERROR':
                log_data["error"] = {
                    "type": random.choice(["NullPointerException", "SQLException", "TimeoutException"]),
                    "message": "An error occurred during processing",
                    "stack_trace": "at com.example.Service.process(Service.java:123)"
                }
                
            samples.append({
                "message": json.dumps(log_data),
                "source": "json-app",
                "timestamp": self.generate_timestamp()
            })
        return samples
    
    def generate_iot_sensor(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate IoT sensor data logs"""
        samples = []
        sensor_types = ['temperature', 'humidity', 'pressure', 'motion', 'light']
        locations = ['warehouse-1', 'office-2', 'datacenter-3', 'factory-4']
        
        for _ in range(count):
            sensor_type = random.choice(sensor_types)
            value = 0
            unit = ""
            
            if sensor_type == 'temperature':
                value = random.uniform(15, 35)
                unit = "celsius"
            elif sensor_type == 'humidity':
                value = random.uniform(20, 80)
                unit = "percent"
            elif sensor_type == 'pressure':
                value = random.uniform(980, 1040)
                unit = "hPa"
            elif sensor_type == 'motion':
                value = random.choice([0, 1])
                unit = "boolean"
            elif sensor_type == 'light':
                value = random.uniform(0, 1000)
                unit = "lux"
                
            samples.append({
                "message": json.dumps({
                    "sensor_id": f"sensor_{random.randint(1000,9999)}",
                    "type": sensor_type,
                    "value": value,
                    "unit": unit,
                    "location": random.choice(locations),
                    "timestamp": self.generate_timestamp(),
                    "battery_level": random.uniform(0, 100),
                    "signal_strength": random.randint(-90, -30)
                }),
                "source": "iot-sensor",
                "timestamp": self.generate_timestamp()
            })
        return samples

def generate_source_specific_samples():
    """Generate separate sample files for each log source type"""
    generator = DiverseLogGenerator()
    
    print("Generating source-specific log sample files...")
    print("=" * 60)
    
    # Define generators with output filenames and counts
    generators = [
        ("aws-cloudtrail-large.ndjson", "AWS CloudTrail", generator.generate_aws_cloudtrail, 1000),
        ("windows-security-large.ndjson", "Windows Security", generator.generate_windows_security, 1000),
        ("zeek-ids-large.ndjson", "Zeek IDS", generator.generate_zeek_ids, 1000),
        ("kubernetes-audit-large.ndjson", "Kubernetes Audit", generator.generate_kubernetes, 1000),
        ("aws-vpcflow-large.ndjson", "AWS VPC Flow Logs", generator.generate_vpc_flow_logs, 1000),
        ("apache-combined-large.ndjson", "Apache Combined", generator.generate_apache_combined, 1000),
        ("linux-auditd-large.ndjson", "Linux Auditd", generator.generate_linux_auditd, 1000),
        ("cef-format-large.ndjson", "CEF Format", generator.generate_cef_logs, 1000),
        ("json-structured-large.ndjson", "JSON Structured Apps", generator.generate_json_structured, 1000),
        ("iot-sensor-large.ndjson", "IoT Sensor Data", generator.generate_iot_sensor, 1000)
    ]
    
    import os
    os.makedirs("samples/large", exist_ok=True)
    
    total_samples = 0
    
    for filename, name, gen_func, count in generators:
        print(f"\n📝 Generating {name}...")
        print(f"   Target: {count} samples")
        
        # Reset timestamp for each file to have consistent time series
        generator.start_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        
        # Generate samples for this specific source
        samples = gen_func(count)
        total_samples += len(samples)
        
        # Save to source-specific file
        output_file = f"samples/large/{filename}"
        with open(output_file, 'w') as f:
            for sample in samples:
                f.write(json.dumps(sample) + '\n')
        
        print(f"   ✅ Saved {len(samples)} samples to {output_file}")
        
        # Show sample of the first log for verification
        if samples:
            first_msg = samples[0].get('message', '')
            if len(first_msg) > 100:
                first_msg = first_msg[:100] + "..."
            print(f"   Sample: {first_msg}")
    
    print("\n" + "=" * 60)
    print(f"✅ COMPLETE: Generated {total_samples} total samples")
    print(f"📁 Files saved to: samples/large/")
    print("\nGenerated files:")
    for filename, name, _, count in generators:
        print(f"  - {filename:<35} ({count:,} samples)")
    
    return total_samples

def generate_comprehensive_samples():
    """Legacy function - now calls source-specific generator"""
    return generate_source_specific_samples()

if __name__ == "__main__":
    samples = generate_comprehensive_samples()