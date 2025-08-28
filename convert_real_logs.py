#!/usr/bin/env python3
"""
Convert real log files to DFE schema NDJSON format

Converts logs from LogHub datasets to match the DFE schema with all necessary fields
including timestamps, hostname, source, and additional metadata.
"""

import json
import re
from datetime import datetime, timedelta
import random
import hashlib
import sys

class LogConverter:
    """Convert various log formats to DFE schema"""
    
    def __init__(self):
        self.start_time = datetime.now() - timedelta(days=7)
        self.hostnames = {
            'apache': 'web-server-01.corp.local',
            'ssh': 'ssh-bastion-01.corp.local',
            'openstack': 'openstack-controller.corp.local'
        }
        
    def generate_timestamp(self):
        """Generate incrementing timestamp"""
        self.start_time += timedelta(seconds=random.randint(1, 10))
        return self.start_time
    
    def create_dfe_log(self, message, source_type, hostname=None, severity='info'):
        """Create DFE schema log entry"""
        timestamp = self.generate_timestamp()
        timestamp_str = timestamp.isoformat() + 'Z'
        
        # Map severity to numeric value
        severity_map = {
            'debug': '7', 'info': '6', 'notice': '5', 'warning': '4',
            'warn': '4', 'error': '3', 'err': '3', 'crit': '2', 
            'alert': '1', 'emerg': '0', 'fatal': '0'
        }
        
        severity_num = severity_map.get(severity.lower(), '6')
        
        # Create event hash
        event_hash = hashlib.md5(f"{timestamp_str}{message}".encode()).hexdigest()
        
        log_entry = {
            "@timestamp": timestamp_str,
            "event_hash": event_hash,
            "facility": "16",
            "facility_label": "local0",
            "hostname": hostname or self.hostnames.get(source_type, 'unknown.corp.local'),
            "logoriginal": f"<{134 + int(severity_num)}>{timestamp.strftime('%b %d %Y %H:%M:%S')}: {message}",
            "logsource": hostname or self.hostnames.get(source_type, 'unknown.corp.local'),
            "msg": message,
            "message": message,
            "org_id": "enterprise",
            "port": 514,
            "priority": str(134 + int(severity_num)),
            "program": source_type.upper(),
            "relayhost": "10.1.1.1",
            "relayip": "10.1.1.1",
            "relayip_enrich": {
                "country_name": "Private Address Space",
                "private_address": True
            },
            "relayip_ip4": "10.1.1.1",
            "severity": severity_num,
            "severity_label": severity,
            "source_type": source_type,
            "tags": {
                "collector": {
                    "host": "127.0.0.1",
                    "hostname": "syslog-collector",
                    "source": "file",
                    "timestamp": timestamp_str,
                    "timezone": "UTC"
                },
                "event": {
                    "category": f"logs_{source_type}",
                    "org_id": "enterprise",
                    "site_id": "hq",
                    "type": f"event.{source_type}.real"
                },
                "replayed": False
            },
            "timestamp": timestamp_str,
            "timestamp_epochms": int(timestamp.timestamp() * 1000),
            "timestamp_finalise": (timestamp + timedelta(seconds=1)).isoformat() + 'Z',
            "timestamp_load": (timestamp + timedelta(seconds=2)).isoformat() + 'Z',
            "timestamp_received": timestamp_str,
            "timestamp_received_epochms": int(timestamp.timestamp() * 1000)
        }
        
        return log_entry
    
    def convert_apache_log(self, input_file, output_file):
        """Convert Apache log to DFE schema"""
        print(f"Converting Apache logs from {input_file}...")
        
        # Apache log patterns
        apache_pattern = re.compile(
            r'\[(.*?)\] \[(.*?)\] (.*)'
        )
        
        converted = []
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # Detect severity from Apache logs
                severity = 'info'
                if '[error]' in line or '[ERROR]' in line:
                    severity = 'error'
                elif '[warn]' in line or '[WARNING]' in line:
                    severity = 'warning'
                elif '[notice]' in line or '[NOTICE]' in line:
                    severity = 'notice'
                elif '[debug]' in line or '[DEBUG]' in line:
                    severity = 'debug'
                elif '[crit]' in line or '[CRITICAL]' in line:
                    severity = 'crit'
                    
                log_entry = self.create_dfe_log(line, 'apache', severity=severity)
                
                # Add Apache-specific fields
                match = apache_pattern.match(line)
                if match:
                    log_entry['apache'] = {
                        'timestamp': match.group(1),
                        'level': match.group(2),
                        'message': match.group(3)
                    }
                
                converted.append(log_entry)
        
        # Write NDJSON
        with open(output_file, 'w') as f:
            for entry in converted:
                f.write(json.dumps(entry) + '\n')
                
        print(f"  ✅ Converted {len(converted)} Apache log entries to {output_file}")
        return len(converted)
    
    def convert_ssh_log(self, input_file, output_file):
        """Convert SSH log to DFE schema"""
        print(f"Converting SSH logs from {input_file}...")
        
        converted = []
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # Detect severity and extract fields from SSH logs
                severity = 'info'
                if 'Failed' in line or 'Invalid' in line or 'Bad' in line:
                    severity = 'warning'
                elif 'error' in line.lower():
                    severity = 'error'
                elif 'Accepted' in line:
                    severity = 'notice'
                    
                log_entry = self.create_dfe_log(line, 'ssh', severity=severity)
                
                # Add SSH-specific fields
                ssh_fields = {}
                
                # Extract IP addresses
                ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
                ips = ip_pattern.findall(line)
                if ips:
                    ssh_fields['source_ip'] = ips[0]
                    
                # Extract usernames
                user_pattern = re.compile(r'user\s+(\w+)|for\s+(\w+)|User\s+(\w+)')
                user_match = user_pattern.search(line)
                if user_match:
                    ssh_fields['username'] = next(g for g in user_match.groups() if g)
                    
                # Extract ports
                port_pattern = re.compile(r'port\s+(\d+)')
                port_match = port_pattern.search(line)
                if port_match:
                    ssh_fields['port'] = port_match.group(1)
                    
                if ssh_fields:
                    log_entry['ssh'] = ssh_fields
                    
                converted.append(log_entry)
        
        # Write NDJSON
        with open(output_file, 'w') as f:
            for entry in converted:
                f.write(json.dumps(entry) + '\n')
                
        print(f"  ✅ Converted {len(converted)} SSH log entries to {output_file}")
        return len(converted)
    
    def convert_openstack_log(self, input_file, output_file):
        """Convert OpenStack log to DFE schema"""
        print(f"Converting OpenStack logs from {input_file}...")
        
        converted = []
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # Detect severity from OpenStack logs
                severity = 'info'
                if 'ERROR' in line:
                    severity = 'error'
                elif 'WARNING' in line or 'WARN' in line:
                    severity = 'warning'
                elif 'DEBUG' in line:
                    severity = 'debug'
                elif 'CRITICAL' in line:
                    severity = 'crit'
                    
                log_entry = self.create_dfe_log(line, 'openstack', severity=severity)
                
                # Add OpenStack-specific fields
                openstack_fields = {}
                
                # Extract service names (nova, neutron, glance, etc)
                service_pattern = re.compile(r'(nova|neutron|glance|keystone|cinder|swift|heat|horizon)')
                service_match = service_pattern.search(line.lower())
                if service_match:
                    openstack_fields['service'] = service_match.group(1)
                    
                # Extract request IDs
                req_pattern = re.compile(r'req-[a-f0-9-]+')
                req_match = req_pattern.search(line)
                if req_match:
                    openstack_fields['request_id'] = req_match.group(0)
                    
                # Extract instance IDs
                instance_pattern = re.compile(r'instance[:\s]+([a-f0-9-]+)')
                instance_match = instance_pattern.search(line)
                if instance_match:
                    openstack_fields['instance_id'] = instance_match.group(1)
                    
                if openstack_fields:
                    log_entry['openstack'] = openstack_fields
                    
                converted.append(log_entry)
        
        # Write NDJSON
        with open(output_file, 'w') as f:
            for entry in converted:
                f.write(json.dumps(entry) + '\n')
                
        print(f"  ✅ Converted {len(converted)} OpenStack log entries to {output_file}")
        return len(converted)

def main():
    """Main conversion process"""
    converter = LogConverter()
    
    print("=" * 60)
    print("CONVERTING REAL LOGS TO DFE SCHEMA FORMAT")
    print("=" * 60)
    
    total_converted = 0
    
    # Convert Apache logs
    if True:
        count = converter.convert_apache_log(
            'samples/real/Apache.log',
            'samples/large/apache-real.ndjson'
        )
        total_converted += count
    
    # Convert SSH logs  
    if True:
        # Reset timestamp for consistent time series
        converter.start_time = datetime.now() - timedelta(days=7)
        count = converter.convert_ssh_log(
            'samples/real/SSH.log',
            'samples/large/ssh-real.ndjson'
        )
        total_converted += count
    
    # Convert OpenStack logs
    if True:
        # Reset timestamp for consistent time series
        converter.start_time = datetime.now() - timedelta(days=7)
        
        # Convert normal logs
        count = converter.convert_openstack_log(
            'samples/real/openstack_normal1.log',
            'samples/large/openstack-normal-real.ndjson'
        )
        total_converted += count
        
        # Convert abnormal logs
        converter.start_time = datetime.now() - timedelta(days=3)
        count = converter.convert_openstack_log(
            'samples/real/openstack_abnormal.log',
            'samples/large/openstack-abnormal-real.ndjson'
        )
        total_converted += count
    
    print("\n" + "=" * 60)
    print(f"✅ CONVERSION COMPLETE")
    print(f"   Total entries converted: {total_converted:,}")
    print(f"   Files saved to: samples/large/")
    print("=" * 60)

if __name__ == "__main__":
    main()