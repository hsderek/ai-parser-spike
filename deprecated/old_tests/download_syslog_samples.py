#!/usr/bin/env python3
"""
Comprehensive Syslog Sample Downloader and Generator

Downloads large varied syslog datasets from public sources and generates 
realistic synthetic samples using faker. Creates standardized JSON format 
samples for VRL testing.

Key Sources:
- LogHub (logpai/loghub) - Academic log datasets
- SecRepo - Security data samples
- Cisco ASA generator examples
- Faker-based synthetic generation

Output: ./samples/*.ndjson files in standardized format
"""

import os
import sys
import json
import requests
import zipfile
import tarfile
import gzip
import shutil
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import subprocess
from urllib.parse import urlparse

# Add faker for realistic synthetic data
try:
    from faker import Faker
    from faker.providers import internet, date_time
except ImportError:
    print("Installing faker...")
    subprocess.run([sys.executable, "-m", "pip", "install", "faker"], check=True)
    from faker import Faker
    from faker.providers import internet, date_time

fake = Faker()
fake.add_provider(internet)
fake.add_provider(date_time)

class SyslogSampleDownloader:
    """Downloads and processes large syslog datasets from public sources"""
    
    def __init__(self, output_dir: str = "./samples"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create temp directory for downloads
        self.temp_dir = Path("./.tmp/downloads")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def download_loghub_datasets(self) -> List[Path]:
        """Download system log datasets from LogHub repository"""
        print("🔄 Downloading LogHub datasets...")
        
        # LogHub known dataset URLs (from their wiki)
        datasets = [
            {
                "name": "Apache",
                "url": "https://zenodo.org/record/3227177/files/Apache.tar.gz",
                "description": "Apache web server logs"
            },
            {
                "name": "OpenStack",
                "url": "https://zenodo.org/record/3227177/files/OpenStack.tar.gz", 
                "description": "OpenStack cloud platform logs"
            },
            {
                "name": "Thunderbird",
                "url": "https://zenodo.org/record/3227177/files/Thunderbird.tar.gz",
                "description": "Mozilla Thunderbird logs"
            }
        ]
        
        downloaded_files = []
        
        for dataset in datasets:
            print(f"📥 Downloading {dataset['name']} - {dataset['description']}")
            
            try:
                response = self.session.get(dataset['url'], timeout=60)
                response.raise_for_status()
                
                # Save archive
                archive_path = self.temp_dir / f"{dataset['name']}.tar.gz"
                with open(archive_path, 'wb') as f:
                    f.write(response.content)
                
                # Extract and process
                extracted_dir = self.temp_dir / dataset['name']
                with tarfile.open(archive_path, 'r:gz') as tar:
                    tar.extractall(extracted_dir)
                
                # Find log files and convert to standard format
                log_files = list(extracted_dir.rglob("*.log"))
                log_files.extend(list(extracted_dir.rglob("*.txt")))
                
                for log_file in log_files[:3]:  # Limit to first 3 files per dataset
                    if log_file.stat().st_size > 0:
                        output_file = self.process_raw_logs(log_file, dataset['name'])
                        if output_file:
                            downloaded_files.append(output_file)
                
                print(f"✅ Processed {dataset['name']}: {len(log_files)} files found")
                
            except Exception as e:
                print(f"❌ Failed to download {dataset['name']}: {e}")
                continue
        
        return downloaded_files
    
    def download_secrepo_samples(self) -> List[Path]:
        """Download security log samples from SecRepo"""
        print("🔄 Downloading SecRepo security samples...")
        
        # Direct links to known SecRepo datasets
        secrepo_urls = [
            "https://www.secrepo.com/self.logs/Syslog/syslog_samples.zip",
            "https://www.secrepo.com/self.logs/auth.log.gz",
            "https://www.secrepo.com/self.logs/kern.log.gz"
        ]
        
        downloaded_files = []
        
        for url in secrepo_urls:
            try:
                print(f"📥 Downloading from SecRepo: {url}")
                
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                
                filename = Path(urlparse(url).path).name
                file_path = self.temp_dir / filename
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                # Process based on file type
                if filename.endswith('.zip'):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(self.temp_dir / "secrepo")
                    
                    # Process extracted files
                    for log_file in (self.temp_dir / "secrepo").rglob("*"):
                        if log_file.is_file() and log_file.suffix in ['.log', '.txt', '']:
                            output_file = self.process_raw_logs(log_file, "secrepo")
                            if output_file:
                                downloaded_files.append(output_file)
                
                elif filename.endswith('.gz'):
                    # Decompress and process
                    decompressed = self.temp_dir / filename.replace('.gz', '')
                    with gzip.open(file_path, 'rb') as f_in:
                        with open(decompressed, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    output_file = self.process_raw_logs(decompressed, "secrepo")
                    if output_file:
                        downloaded_files.append(output_file)
                
            except Exception as e:
                print(f"❌ Failed to download from SecRepo {url}: {e}")
                continue
        
        return downloaded_files
    
    def process_raw_logs(self, log_file: Path, source_name: str) -> Optional[Path]:
        """Process raw log files into standardized JSON format"""
        try:
            # Read and parse log file
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if len(lines) < 10:  # Skip tiny files
                return None
            
            # Generate output filename
            output_file = self.output_dir / f"{source_name}-{log_file.stem}-raw.ndjson"
            processed_count = 0
            
            with open(output_file, 'w') as out_f:
                for line in lines[:1000]:  # Limit to first 1000 lines
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Try to detect if it's already structured or raw syslog
                    if line.startswith('{'):
                        # Already JSON, validate and possibly reformat
                        try:
                            data = json.loads(line)
                            # Convert to our standard format
                            if 'message' not in data and ('msg' in data or 'content' in data):
                                data['message'] = data.get('msg', data.get('content', line))
                            if 'timestamp' not in data:
                                data['timestamp'] = datetime.now().isoformat() + 'Z'
                            
                            out_f.write(json.dumps(data) + '\n')
                            processed_count += 1
                        except json.JSONDecodeError:
                            continue
                    else:
                        # Raw log line, convert to standard format
                        timestamp = self.extract_timestamp(line)
                        if not timestamp:
                            timestamp = datetime.now().isoformat() + 'Z'
                        
                        record = {
                            "message": line,
                            "timestamp": timestamp,
                            "source": source_name
                        }
                        
                        out_f.write(json.dumps(record) + '\n')
                        processed_count += 1
            
            if processed_count > 0:
                print(f"✅ Processed {log_file.name}: {processed_count} records → {output_file.name}")
                return output_file
            else:
                output_file.unlink()  # Remove empty file
                return None
                
        except Exception as e:
            print(f"❌ Failed to process {log_file}: {e}")
            return None
    
    def extract_timestamp(self, log_line: str) -> Optional[str]:
        """Extract timestamp from log line and convert to ISO format"""
        # Common syslog timestamp patterns
        patterns = [
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',  # Jan 01 12:34:56
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',   # 2024-01-01T12:34:56
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',  # 2024-01-01 12:34:56
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_line)
            if match:
                try:
                    # Convert to ISO format (simplified)
                    return datetime.now().isoformat() + 'Z'
                except:
                    continue
        
        return None


class SyslogSyntheticGenerator:
    """Generate realistic synthetic syslog samples using faker"""
    
    def __init__(self, output_dir: str = "./samples"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.fake = Faker()
        
        # Network equipment hostnames
        self.hostnames = [
            "asa-01.corp.local", "asa-02.corp.local", "fw-edge-01", "fw-dmz-01",
            "rtr-core-01", "rtr-branch-01", "sw-core-01", "sw-access-01",
            "fortigate-01.local", "checkpoint-gw01", "palo-pa-01"
        ]
        
        # IP ranges for realistic networks
        self.internal_ips = ["192.168.1.", "10.0.0.", "172.16.1."]
        self.external_ips = ["203.0.113.", "198.51.100.", "8.8.8.", "1.1.1."]
        
    def generate_cisco_asa_logs(self, count: int = 1000) -> Path:
        """Generate realistic Cisco ASA firewall logs"""
        output_file = self.output_dir / "synthetic-cisco-asa-raw.ndjson"
        
        # ASA message templates with realistic variety
        asa_templates = [
            # Deny traffic
            "%ASA-4-106023: Deny {protocol} src {src_zone}:{src_ip}/{src_port} dst {dst_zone}:{dst_ip}/{dst_port} by access-group \"{acl}\" [0x0, 0x0]",
            "%ASA-4-106100: access-list {acl} denied {protocol} {src_zone}/{src_ip}({src_port}) -> {dst_zone}/{dst_ip}({dst_port}) hit-cnt 1 first hit [0x{hex1}, 0x{hex2}]",
            
            # Allow/Build connections
            "%ASA-6-302013: Built {direction} {protocol} connection {conn_id} for {src_zone}:{src_ip}/{src_port} ({src_nat_ip}/{src_nat_port}) to {dst_zone}:{dst_ip}/{dst_port} ({dst_nat_ip}/{dst_nat_port})",
            "%ASA-6-302015: Built {direction} {protocol} connection {conn_id} for {src_zone}:{src_ip}/{src_port} ({src_nat_ip}/{src_nat_port}) to {dst_zone}:{dst_ip}/{dst_port} ({dst_nat_ip}/{dst_nat_port})",
            
            # Teardown connections  
            "%ASA-6-302014: Teardown {protocol} connection {conn_id} for {src_zone}:{src_ip}/{src_port} to {dst_zone}:{dst_ip}/{dst_port} duration {duration} bytes {bytes_sent} ({reason})",
            
            # Authentication
            "%ASA-6-109005: Authentication succeeded for user '{username}' from {src_ip}/{src_port} to {dst_ip}/{dst_port} on interface {interface}",
            "%ASA-4-109006: Authentication failed for user '{username}' from {src_ip}/{src_port} to {dst_ip}/{dst_port} on interface {interface}",
            
            # VPN
            "%ASA-6-722022: Group <{vpn_group}> User <{username}> IP <{user_ip}> IPv4 Address <{assigned_ip}> assigned to session",
            "%ASA-4-722037: Group <{vpn_group}> User <{username}> IP <{user_ip}> Session terminated: User requested",
            
            # System events
            "%ASA-5-111008: User '{username}' executed the '{command}' command",
            "%ASA-3-313001: Denied ICMP type={icmp_type}, code={icmp_code} from {src_ip} on interface {interface}",
        ]
        
        with open(output_file, 'w') as f:
            for _ in range(count):
                template = random.choice(asa_templates)
                
                # Generate realistic values
                values = {
                    'protocol': random.choice(['tcp', 'udp', 'icmp']),
                    'src_zone': random.choice(['outside', 'inside', 'dmz']),
                    'dst_zone': random.choice(['outside', 'inside', 'dmz']),
                    'src_ip': self.generate_ip(),
                    'dst_ip': self.generate_ip(),
                    'src_port': random.randint(1024, 65535),
                    'dst_port': random.choice([22, 23, 25, 53, 80, 110, 143, 443, 993, 995]),
                    'src_nat_ip': self.generate_ip(True),
                    'dst_nat_ip': self.generate_ip(True),
                    'src_nat_port': random.randint(1024, 65535),
                    'dst_nat_port': random.choice([22, 23, 25, 53, 80, 110, 143, 443, 993, 995]),
                    'acl': random.choice(['outside_access_in', 'inside_access_out', 'dmz_access_in', 'global_policy']),
                    'conn_id': random.randint(10000, 99999),
                    'direction': random.choice(['inbound', 'outbound']),
                    'duration': f"{random.randint(1, 3600):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}",
                    'bytes_sent': random.randint(64, 1048576),
                    'reason': random.choice(['TCP FINs', 'TCP RSTs', 'Idle timeout', 'User requested']),
                    'username': self.fake.user_name(),
                    'interface': random.choice(['outside', 'inside', 'dmz']),
                    'vpn_group': random.choice(['SSL_VPN', 'IPSEC_VPN', 'Remote_Users']),
                    'user_ip': self.generate_external_ip(),
                    'assigned_ip': self.generate_internal_ip(),
                    'command': random.choice(['show version', 'show running-config', 'write memory', 'ping']),
                    'icmp_type': random.randint(0, 18),
                    'icmp_code': random.randint(0, 15),
                    'hex1': format(random.randint(0, 255), '02x'),
                    'hex2': format(random.randint(0, 255), '02x'),
                }
                
                try:
                    message_content = template.format(**values)
                    syslog_priority = random.choice([131, 132, 133, 134, 135, 136])  # Various ASA severities
                    hostname = random.choice(self.hostnames[:2])  # Use ASA hostnames
                    
                    timestamp_dt = self.fake.date_time_between(start_date='-7d', end_date='now')
                    timestamp_str = timestamp_dt.strftime('%b %d %Y %H:%M:%S')
                    
                    full_message = f"<{syslog_priority}>{timestamp_str} {hostname}: {message_content}"
                    
                    record = {
                        "message": full_message,
                        "timestamp": timestamp_dt.isoformat() + 'Z'
                    }
                    
                    f.write(json.dumps(record) + '\n')
                    
                except KeyError as e:
                    # Skip malformed templates
                    continue
        
        print(f"✅ Generated {count} synthetic Cisco ASA logs → {output_file.name}")
        return output_file
    
    def generate_fortigate_logs(self, count: int = 500) -> Path:
        """Generate realistic FortiGate firewall logs"""
        output_file = self.output_dir / "synthetic-fortigate-raw.ndjson"
        
        # FortiGate log templates
        fortigate_templates = [
            "date={date} time={time} devname=\"{hostname}\" devid=\"{devid}\" logid=\"{logid}\" type=\"traffic\" subtype=\"forward\" level=\"notice\" vd=\"root\" eventtime={eventtime} tz=\"{tz}\" srcip={src_ip} srcport={src_port} srcintf=\"{src_intf}\" srcintfrole=\"{src_role}\" dstip={dst_ip} dstport={dst_port} dstintf=\"{dst_intf}\" dstintfrole=\"{dst_role}\" poluuid=\"{pol_uuid}\" sessionid={session_id} proto={proto_num} action=\"{action}\" policyid={policy_id} policytype=\"policy\" service=\"{service}\" dstcountry=\"{dst_country}\" srccountry=\"{src_country}\" trandisp=\"noop\" duration={duration} sentbyte={sent_bytes} rcvdbyte={rcvd_bytes} sentpkt={sent_pkts} rcvdpkt={rcvd_pkts}",
            "date={date} time={time} devname=\"{hostname}\" devid=\"{devid}\" logid=\"{logid}\" type=\"utm\" subtype=\"virus\" eventtype=\"infected\" level=\"warning\" vd=\"root\" eventtime={eventtime} tz=\"{tz}\" msg=\"File is infected.\" action=\"blocked\" service=\"{service}\" sessionid={session_id} srcip={src_ip} dstip={dst_ip} srcport={src_port} dstport={dst_port} srcintf=\"{src_intf}\" srcintfrole=\"{src_role}\" dstintf=\"{dst_intf}\" dstintfrole=\"{dst_role}\" proto={proto_num} direction=\"{direction}\" filename=\"{filename}\" virus=\"{virus_name}\" dtype=\"Virus\" ref=\"http://www.fortiguard.com/encyclopedia/virus/{virus_id}\" virusid={virus_id} url=\"{url}\" profile=\"{profile}\" agent=\"{user_agent}\" analyticssubmit=\"false\" crscore=50 craction=2 crlevel=\"high\"",
        ]
        
        with open(output_file, 'w') as f:
            for _ in range(count):
                template = random.choice(fortigate_templates)
                
                now = self.fake.date_time_between(start_date='-7d', end_date='now')
                
                values = {
                    'date': now.strftime('%Y-%m-%d'),
                    'time': now.strftime('%H:%M:%S'),
                    'hostname': random.choice(['FGT-01', 'FGT-Edge', 'FortiGate-100F']),
                    'devid': f"FG{random.randint(100, 999)}E{random.randint(10000, 99999)}",
                    'logid': f"0000000{random.randint(10, 99)}",
                    'eventtime': str(int(now.timestamp())),
                    'tz': "+0000",
                    'src_ip': self.generate_ip(),
                    'dst_ip': self.generate_ip(),
                    'src_port': random.randint(1024, 65535),
                    'dst_port': random.choice([22, 25, 53, 80, 110, 143, 443, 993, 995]),
                    'src_intf': random.choice(['wan1', 'wan2', 'internal', 'dmz']),
                    'dst_intf': random.choice(['wan1', 'wan2', 'internal', 'dmz']),
                    'src_role': random.choice(['wan', 'lan', 'dmz']),
                    'dst_role': random.choice(['wan', 'lan', 'dmz']),
                    'pol_uuid': f"{self.fake.uuid4()}",
                    'session_id': random.randint(100000, 999999),
                    'proto_num': random.choice([6, 17, 1]),  # TCP, UDP, ICMP
                    'action': random.choice(['accept', 'deny', 'block']),
                    'policy_id': random.randint(1, 100),
                    'service': random.choice(['HTTP', 'HTTPS', 'SSH', 'DNS', 'SMTP']),
                    'dst_country': random.choice(['United States', 'Reserved', 'United Kingdom', 'Germany']),
                    'src_country': random.choice(['United States', 'Reserved', 'China', 'Russia']),
                    'duration': random.randint(1, 3600),
                    'sent_bytes': random.randint(64, 1048576),
                    'rcvd_bytes': random.randint(64, 1048576),
                    'sent_pkts': random.randint(1, 1000),
                    'rcvd_pkts': random.randint(1, 1000),
                    'direction': random.choice(['inbound', 'outbound']),
                    'filename': self.fake.file_name(),
                    'virus_name': random.choice(['W32/Conficker', 'Trojan.Generic', 'Adware.Win32', 'JS/Suspicious']),
                    'virus_id': random.randint(10000, 99999),
                    'url': self.fake.url(),
                    'profile': random.choice(['default', 'strict', 'custom']),
                    'user_agent': self.fake.user_agent(),
                }
                
                try:
                    log_content = template.format(**values)
                    
                    # FortiGate logs don't use traditional syslog format, they're direct CEF/key-value
                    record = {
                        "message": log_content,
                        "timestamp": now.isoformat() + 'Z'
                    }
                    
                    f.write(json.dumps(record) + '\n')
                    
                except KeyError:
                    continue
        
        print(f"✅ Generated {count} synthetic FortiGate logs → {output_file.name}")
        return output_file
    
    def generate_checkpoint_logs(self, count: int = 500) -> Path:
        """Generate realistic CheckPoint firewall logs"""
        output_file = self.output_dir / "synthetic-checkpoint-raw.ndjson"
        
        # CheckPoint SmartEvent log templates
        checkpoint_templates = [
            "time=\"{time}\" hostname={hostname} product=\"VPN-1 & FireWall-1\" action=\"{action}\" orig=\"{src_ip}\" xlatesrc=\"{src_nat}\" dst=\"{dst_ip}\" xlatedst=\"{dst_nat}\" proto=\"{protocol}\" service=\"{dst_port}\" xlatesport=\"{src_port}\" rule=\"{rule_num}\" rule_uid=\"{rule_uid}\" starttime=\"{starttime}\" endtime=\"{endtime}\" bytes=\"{bytes}\" packets=\"{packets}\" loguid=\"{{{log_uid}}}\" interface_name=\"{interface}\" interface_dir=\"{direction}\" has_accounting=\"0\" uuid=\"<{uuid}>\"",
            "time=\"{time}\" hostname={hostname} product=\"SmartDefense\" attack=\"{attack_name}\" attack_info=\"{attack_info}\" severity=\"{severity}\" protection_id=\"{protection_id}\" protection_type=\"{protection_type}\" smartdefense_profile=\"{profile}\" src=\"{src_ip}\" dst=\"{dst_ip}\" proto=\"{protocol}\" service=\"{dst_port}\" rule=\"{rule_num}\" rule_uid=\"{rule_uid}\" action=\"{action}\" loguid=\"{{{log_uid}}}\" uuid=\"<{uuid}>\"",
        ]
        
        with open(output_file, 'w') as f:
            for _ in range(count):
                template = random.choice(checkpoint_templates)
                
                now = self.fake.date_time_between(start_date='-7d', end_date='now')
                
                values = {
                    'time': now.strftime('%d%b%Y %H:%M:%S'),
                    'hostname': random.choice(['CP-GW01', 'checkpoint-fw', 'CPGW-DMZ']),
                    'action': random.choice(['accept', 'drop', 'reject', 'block']),
                    'src_ip': self.generate_ip(),
                    'dst_ip': self.generate_ip(), 
                    'src_nat': self.generate_external_ip(),
                    'dst_nat': self.generate_ip(),
                    'protocol': random.choice(['tcp', 'udp', 'icmp']),
                    'dst_port': random.choice([22, 25, 53, 80, 110, 143, 443, 993, 995]),
                    'src_port': random.randint(1024, 65535),
                    'rule_num': random.randint(1, 50),
                    'rule_uid': f"{{{self.fake.uuid4()}}}",
                    'starttime': now.strftime('%d%b%Y %H:%M:%S'),
                    'endtime': (now + timedelta(seconds=random.randint(1, 300))).strftime('%d%b%Y %H:%M:%S'),
                    'bytes': random.randint(64, 1048576),
                    'packets': random.randint(1, 1000),
                    'log_uid': self.fake.uuid4(),
                    'interface': random.choice(['eth0', 'eth1', 'bond0']),
                    'direction': random.choice(['inbound', 'outbound']),
                    'uuid': self.fake.uuid4(),
                    'attack_name': random.choice(['Port Scan', 'Brute Force', 'DoS Attack', 'Malware Communication']),
                    'attack_info': random.choice(['Multiple connection attempts', 'Suspicious pattern detected', 'Known malicious IP']),
                    'severity': random.choice(['Low', 'Medium', 'High', 'Critical']),
                    'protection_id': random.randint(1000, 9999),
                    'protection_type': random.choice(['IPS', 'Anti-Virus', 'Anti-Bot', 'Application Control']),
                    'profile': random.choice(['Standard', 'Strict', 'Custom']),
                }
                
                try:
                    log_content = template.format(**values)
                    syslog_priority = random.choice([131, 132, 133, 134])
                    
                    full_message = f"<{syslog_priority}>{now.strftime('%b %d %H:%M:%S')} {values['hostname']}: {log_content}"
                    
                    record = {
                        "message": full_message,
                        "timestamp": now.isoformat() + 'Z'
                    }
                    
                    f.write(json.dumps(record) + '\n')
                    
                except KeyError:
                    continue
        
        print(f"✅ Generated {count} synthetic CheckPoint logs → {output_file.name}")
        return output_file
    
    def generate_ip(self, external: bool = None) -> str:
        """Generate realistic IP address"""
        if external is None:
            external = random.choice([True, False])
        
        if external:
            return self.generate_external_ip()
        else:
            return self.generate_internal_ip()
    
    def generate_internal_ip(self) -> str:
        """Generate internal IP address"""
        prefix = random.choice(self.internal_ips)
        return prefix + str(random.randint(1, 254))
    
    def generate_external_ip(self) -> str:
        """Generate external IP address"""
        prefix = random.choice(self.external_ips)
        return prefix + str(random.randint(1, 254))


def main():
    """Main execution function"""
    print("🚀 Starting Comprehensive Syslog Sample Collection")
    print("=" * 60)
    
    # Initialize components
    downloader = SyslogSampleDownloader()
    generator = SyslogSyntheticGenerator()
    
    all_generated_files = []
    
    # Download real datasets
    print("\n📥 DOWNLOADING REAL DATASETS")
    print("-" * 40)
    
    try:
        loghub_files = downloader.download_loghub_datasets()
        all_generated_files.extend(loghub_files)
    except Exception as e:
        print(f"❌ LogHub download failed: {e}")
    
    try:
        secrepo_files = downloader.download_secrepo_samples()
        all_generated_files.extend(secrepo_files)
    except Exception as e:
        print(f"❌ SecRepo download failed: {e}")
    
    # Generate synthetic samples
    print("\n🎭 GENERATING SYNTHETIC SAMPLES")
    print("-" * 40)
    
    synthetic_files = [
        generator.generate_cisco_asa_logs(2000),
        generator.generate_fortigate_logs(1000), 
        generator.generate_checkpoint_logs(1000),
    ]
    all_generated_files.extend(synthetic_files)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SAMPLE COLLECTION COMPLETE")
    print("=" * 60)
    
    total_files = len([f for f in all_generated_files if f and f.exists()])
    print(f"✅ Total files generated: {total_files}")
    
    print("\n📁 Generated files:")
    for file_path in all_generated_files:
        if file_path and file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            with open(file_path, 'r') as f:
                line_count = sum(1 for _ in f)
            print(f"   {file_path.name}: {line_count:,} records ({size_mb:.1f}MB)")
    
    # Cleanup temp files
    temp_dir = Path("./.tmp/downloads")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up temporary files from {temp_dir}")
    
    print(f"\n🎯 All samples ready in ./samples/ directory for VRL testing!")


if __name__ == "__main__":
    main()