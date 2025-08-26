#!/usr/bin/env python3
"""
Generate Large Syslog Samples

Creates large, varied syslog datasets matching our existing sample types:
- Cisco ASA (similar to cisco-asa-raw.ndjson)
- Cisco IOS (similar to cisco-ios-raw.ndjson)
- FortiGate 
- CheckPoint

Uses faker for realistic synthetic data generation.
Output: ./samples/*-large.ndjson files in standardized format
"""

import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker
from faker.providers import internet, date_time

fake = Faker()
fake.add_provider(internet)
fake.add_provider(date_time)

class LargeSyslogGenerator:
    """Generate large realistic syslog samples matching existing sample types"""
    
    def __init__(self, output_dir: str = "./samples"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.fake = Faker()
        
        # Network equipment hostnames matching existing samples
        self.asa_hostnames = ["asa-01.corp.local", "asa-02.corp.local", "asa-edge-01"]
        self.ios_hostnames = ["rtr-01.corp.local", "sw-core-01", "rtr-branch-01"]
        self.fortigate_hostnames = ["FGT-01", "FortiGate-100F", "FGT-Edge"]
        self.checkpoint_hostnames = ["CP-GW01", "checkpoint-gw01", "CPGW-DMZ"]
        
        # IP ranges for realistic networks
        self.internal_networks = ["192.168.1.", "192.168.50.", "10.0.0.", "172.16.1."]
        self.external_networks = ["203.0.113.", "198.51.100.", "8.8.8.", "1.1.1."]
        
    def generate_cisco_asa_large(self, count: int = 5000) -> Path:
        """Generate large Cisco ASA dataset matching cisco-asa-raw.ndjson format"""
        output_file = self.output_dir / "cisco-asa-large.ndjson"
        
        # ASA message templates based on real Cisco ASA syslog patterns
        asa_templates = [
            # Deny traffic (most common)
            ": %ASA-4-106023: Deny {protocol} src {src_zone}:{src_ip}/{src_port} dst {dst_zone}:{dst_ip}/{dst_port} by access-group \"{acl}\" [0x0, 0x0]",
            ": %ASA-4-106100: access-list {acl} denied {protocol} {src_zone}/{src_ip}({src_port}) -> {dst_zone}/{dst_ip}({dst_port}) hit-cnt 1 first hit [0x{hex1}, 0x{hex2}]",
            
            # Built connections
            ": %ASA-3-302013: Built {direction} {protocol} connection {conn_id} for {src_zone}:{src_ip}/{src_port} ({src_nat_ip}/{src_nat_port}) to {dst_zone}:{dst_ip}/{dst_port} ({dst_nat_ip}/{dst_nat_port})",
            ": %ASA-6-302015: Built {direction} {protocol} connection {conn_id} for {src_zone}:{src_ip}/{src_port} ({src_nat_ip}/{src_nat_port}) to {dst_zone}:{dst_ip}/{dst_port} ({dst_nat_ip}/{dst_nat_port})",
            
            # Teardown connections
            ": %ASA-6-302014: Teardown {protocol} connection {conn_id} for {src_zone}:{src_ip}/{src_port} to {dst_zone}:{dst_ip}/{dst_port} duration {duration} bytes {bytes_sent} ({reason})",
            
            # ICMP errors
            ": %ASA-4-313005: No matching connection for ICMP error message: icmp src {src_zone}:{src_ip} dst {dst_zone}:{dst_ip} (type {icmp_type}, code {icmp_code}) on {interface} interface",
            
            # Authentication
            ": %ASA-6-109005: Authentication succeeded for user '{username}' from {src_ip}/{src_port} to {dst_ip}/{dst_port} on interface {interface}",
            ": %ASA-4-109006: Authentication failed for user '{username}' from {src_ip}/{src_port} to {dst_ip}/{dst_port} on interface {interface}",
            
            # VPN events
            ": %ASA-6-722022: Group <{vpn_group}> User <{username}> IP <{user_ip}> IPv4 Address <{assigned_ip}> assigned to session",
            ": %ASA-4-722037: Group <{vpn_group}> User <{username}> IP <{user_ip}> Session terminated: User requested",
            
            # System events
            ": %ASA-5-111008: User '{username}' executed the '{command}' command",
            ": %ASA-3-313001: Denied ICMP type={icmp_type}, code={icmp_code} from {src_ip} on interface {interface}",
            
            # Access list hits
            ": %ASA-4-106023: Deny tcp src {src_zone}:{src_ip}/{src_port} dst {dst_zone}:{dst_ip}/{dst_port} type {msg_type}, code {msg_code} by access-group \"{acl}\"",
        ]
        
        with open(output_file, 'w') as f:
            for _ in range(count):
                template = random.choice(asa_templates)
                
                # Generate timestamp within last 30 days
                timestamp_dt = self.fake.date_time_between(start_date='-30d', end_date='now')
                timestamp_str = timestamp_dt.strftime('%b %d %Y %H:%M:%S')
                
                # Generate realistic values
                values = {
                    'protocol': random.choice(['tcp'] * 60 + ['udp'] * 30 + ['icmp'] * 10),  # Weighted distribution
                    'src_zone': random.choice(['outside'] * 40 + ['inside'] * 30 + ['dmz'] * 20 + ['guest'] * 10),
                    'dst_zone': random.choice(['inside'] * 40 + ['outside'] * 30 + ['dmz'] * 20 + ['guest'] * 10),
                    'src_ip': self.generate_weighted_ip(),
                    'dst_ip': self.generate_weighted_ip(),
                    'src_port': self.generate_realistic_port(high_ports=True),
                    'dst_port': self.generate_realistic_port(high_ports=False),
                    'src_nat_ip': self.generate_external_ip(),
                    'dst_nat_ip': self.generate_external_ip(),
                    'src_nat_port': self.generate_realistic_port(high_ports=True),
                    'dst_nat_port': self.generate_realistic_port(high_ports=False),
                    'acl': random.choice(['outside_access_in'] * 40 + ['inside_access_out'] * 20 + ['dmz_access_in'] * 20 + ['global_policy'] * 10 + ['guest_policy'] * 10),
                    'conn_id': random.randint(10000, 999999),
                    'direction': random.choice(['outbound'] * 60 + ['inbound'] * 40),
                    'duration': f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}",
                    'bytes_sent': random.choice([random.randint(64, 1500)] * 70 + [random.randint(1500, 65536)] * 20 + [random.randint(65536, 1048576)] * 10),
                    'reason': random.choice(['TCP FINs'] * 40 + ['TCP RSTs'] * 30 + ['Idle timeout'] * 20 + ['User requested'] * 10),
                    'username': random.choice([self.fake.user_name() for _ in range(50)] + ['admin', 'user', 'guest', 'service']),
                    'interface': random.choice(['outside', 'inside', 'dmz', 'guest']),
                    'vpn_group': random.choice(['SSL_VPN', 'IPSEC_VPN', 'Remote_Users', 'Contractors']),
                    'user_ip': self.generate_external_ip(),
                    'assigned_ip': self.generate_internal_ip(),
                    'command': random.choice(['show version', 'show running-config', 'write memory', 'ping', 'traceroute', 'show interface', 'show log']),
                    'icmp_type': random.randint(0, 18),
                    'icmp_code': random.randint(0, 15),
                    'hex1': format(random.randint(0, 255), '02x'),
                    'hex2': format(random.randint(0, 255), '02x'),
                    'msg_type': random.randint(0, 18),
                    'msg_code': random.randint(0, 15),
                }
                
                try:
                    message_content = template.format(**values)
                    syslog_priority = random.choice([131] * 20 + [132] * 50 + [133] * 20 + [134] * 10)  # Weighted priorities
                    hostname = random.choice(self.asa_hostnames)
                    
                    full_message = f"<{syslog_priority}>{timestamp_str} {hostname}{message_content}"
                    
                    record = {
                        "message": full_message,
                        "timestamp": timestamp_dt.isoformat() + 'Z'
                    }
                    
                    f.write(json.dumps(record) + '\n')
                    
                except (KeyError, ValueError):
                    # Skip malformed templates
                    continue
        
        print(f"✅ Generated {count} Cisco ASA logs → {output_file.name}")
        return output_file
    
    def generate_cisco_ios_large(self, count: int = 3000) -> Path:
        """Generate large Cisco IOS dataset matching cisco-ios-raw.ndjson format"""
        output_file = self.output_dir / "cisco-ios-large.ndjson"
        
        # IOS message templates based on real Cisco IOS syslog patterns
        ios_templates = [
            ": %SEC-6-IPACCESSLOGP: list {acl_num} {action} {protocol} {src_ip}({src_port}) -> {dst_ip}({dst_port}), {packet_count} packet{plural}",
            ": %LINK-3-UPDOWN: Interface {interface}, changed state to {state}",
            ": %LINEPROTO-5-UPDOWN: Line protocol on Interface {interface}, changed state to {state}",
            ": %SYS-5-CONFIG_I: Configured from {config_source} by {username} on {session_type} ({session_ip})",
            ": %OSPF-5-ADJCHG: Process {process_id}, Nbr {neighbor_ip} on {interface} from {old_state} to {new_state}, {reason}",
            ": %BGP-5-ADJCHANGE: neighbor {neighbor_ip} {state}",
            ": %BGP-4-ADJCHANGE: neighbor {neighbor_ip} Down {reason}",
            ": %DUAL-5-NBRCHANGE: EIGRP-IPv4 {as_num}: Neighbor {neighbor_ip} ({interface}) is {state}: {reason}",
            ": %SYS-6-LOGGINGHOST_STARTSTOP: Logging to host {log_server} {action}",
            ": %SNMP-5-AUTHFAIL: Authentication failure for SNMP req from host {src_ip}",
            ": %SEC-6-IPACCESSLOGDP: list {acl_num} {action} {protocol} {src_ip} -> {dst_ip} ({reason}), {packet_count} packet{plural}",
            ": %SSH-5-SSH2_SESSION: SSH2 Session request from {src_ip} (tty = {tty}) using crypto cipher '{cipher}', hmac '{hmac}'",
        ]
        
        with open(output_file, 'w') as f:
            for _ in range(count):
                template = random.choice(ios_templates)
                
                timestamp_dt = self.fake.date_time_between(start_date='-30d', end_date='now')
                timestamp_str = timestamp_dt.strftime('%b %d %Y %H:%M:%S')
                
                values = {
                    'acl_num': random.choice([101, 102, 110, 120, 'OUTSIDE_IN', 'INSIDE_OUT']),
                    'action': random.choice(['denied'] * 70 + ['permitted'] * 30),
                    'protocol': random.choice(['tcp'] * 60 + ['udp'] * 30 + ['icmp'] * 10),
                    'src_ip': self.generate_weighted_ip(),
                    'dst_ip': self.generate_weighted_ip(),
                    'src_port': self.generate_realistic_port(high_ports=True),
                    'dst_port': self.generate_realistic_port(high_ports=False),
                    'packet_count': random.choice([1] * 80 + list(range(2, 100)) * 20),
                    'plural': lambda: 's' if values.get('packet_count', 1) != 1 else '',
                    'interface': random.choice(['GigabitEthernet0/0', 'GigabitEthernet0/1', 'GigabitEthernet0/2', 'FastEthernet0/0', 'Serial0/0/0', 'Loopback0']),
                    'state': random.choice(['up', 'down', 'administratively down']),
                    'config_source': random.choice(['console', 'vty0', 'vty1', 'memory']),
                    'username': random.choice(['admin', 'cisco', 'user', 'operator', self.fake.user_name()]),
                    'session_type': random.choice(['vty0', 'vty1', 'console']),
                    'session_ip': self.generate_internal_ip(),
                    'process_id': random.randint(1, 100),
                    'neighbor_ip': self.generate_internal_ip(),
                    'old_state': random.choice(['LOADING', 'EXSTART', 'EXCHANGE', 'INIT']),
                    'new_state': random.choice(['FULL', 'DOWN', '2WAY', 'INIT']),
                    'reason': random.choice(['Loading Done', 'Hello received', 'Dead timer expired', 'Interface down']),
                    'as_num': random.randint(1, 65535),
                    'log_server': self.generate_internal_ip(),
                    'tty': random.randint(0, 15),
                    'cipher': random.choice(['aes128-ctr', 'aes192-ctr', 'aes256-ctr', '3des-cbc']),
                    'hmac': random.choice(['hmac-sha1', 'hmac-sha2-256', 'hmac-md5']),
                }
                
                # Handle callable plural
                if 'packet_count' in values:
                    values['plural'] = 's' if values['packet_count'] != 1 else ''
                
                try:
                    message_content = template.format(**values)
                    syslog_priority = random.choice([133] * 30 + [134] * 40 + [189] * 20 + [186] * 10)
                    hostname = random.choice(self.ios_hostnames)
                    
                    full_message = f"<{syslog_priority}>{timestamp_str} {hostname}{message_content}"
                    
                    record = {
                        "message": full_message,
                        "timestamp": timestamp_dt.isoformat() + 'Z'
                    }
                    
                    f.write(json.dumps(record) + '\n')
                    
                except (KeyError, ValueError):
                    continue
        
        print(f"✅ Generated {count} Cisco IOS logs → {output_file.name}")
        return output_file
    
    def generate_fortigate_large(self, count: int = 2000) -> Path:
        """Generate large FortiGate dataset"""
        output_file = self.output_dir / "fortigate-large.ndjson"
        
        # FortiGate log format (CEF-like key=value pairs)
        fortigate_templates = [
            "date={date} time={time} devname=\"{hostname}\" devid=\"{devid}\" logid=\"{logid}\" type=\"traffic\" subtype=\"{subtype}\" level=\"{level}\" vd=\"root\" eventtime={eventtime} srcip={src_ip} srcport={src_port} srcintf=\"{src_intf}\" dstip={dst_ip} dstport={dst_port} dstintf=\"{dst_intf}\" proto={proto_num} action=\"{action}\" policyid={policy_id} service=\"{service}\" trandisp=\"noop\" duration={duration} sentbyte={sent_bytes} rcvdbyte={rcvd_bytes}",
            "date={date} time={time} devname=\"{hostname}\" devid=\"{devid}\" logid=\"{logid}\" type=\"utm\" subtype=\"{utm_type}\" level=\"{level}\" vd=\"root\" eventtime={eventtime} srcip={src_ip} dstip={dst_ip} srcport={src_port} dstport={dst_port} proto={proto_num} action=\"{action}\" service=\"{service}\" direction=\"{direction}\" msg=\"{utm_msg}\"",
        ]
        
        with open(output_file, 'w') as f:
            for _ in range(count):
                template = random.choice(fortigate_templates)
                
                timestamp_dt = self.fake.date_time_between(start_date='-30d', end_date='now')
                
                values = {
                    'date': timestamp_dt.strftime('%Y-%m-%d'),
                    'time': timestamp_dt.strftime('%H:%M:%S'),
                    'hostname': random.choice(self.fortigate_hostnames),
                    'devid': f"FG{random.randint(100, 999)}E{random.randint(10000, 99999)}",
                    'logid': f"0000000{random.randint(10, 99)}",
                    'subtype': random.choice(['forward', 'local', 'multicast', 'broadcast']),
                    'level': random.choice(['notice', 'information', 'warning', 'error']),
                    'eventtime': str(int(timestamp_dt.timestamp())),
                    'src_ip': self.generate_weighted_ip(),
                    'dst_ip': self.generate_weighted_ip(),
                    'src_port': self.generate_realistic_port(high_ports=True),
                    'dst_port': self.generate_realistic_port(high_ports=False),
                    'src_intf': random.choice(['wan1', 'wan2', 'internal', 'dmz']),
                    'dst_intf': random.choice(['wan1', 'wan2', 'internal', 'dmz']),
                    'proto_num': random.choice([6, 17, 1]),  # TCP, UDP, ICMP
                    'action': random.choice(['accept'] * 60 + ['deny'] * 30 + ['block'] * 10),
                    'policy_id': random.randint(1, 100),
                    'service': random.choice(['HTTP', 'HTTPS', 'SSH', 'DNS', 'SMTP', 'FTP', 'TELNET']),
                    'duration': random.randint(1, 3600),
                    'sent_bytes': random.randint(64, 1048576),
                    'rcvd_bytes': random.randint(64, 1048576),
                    'utm_type': random.choice(['virus', 'ips', 'webfilter', 'antispam']),
                    'direction': random.choice(['inbound', 'outbound']),
                    'utm_msg': random.choice(['File is infected', 'Attack detected', 'URL blocked', 'Spam detected']),
                }
                
                try:
                    message_content = template.format(**values)
                    syslog_priority = random.choice([134, 133, 132, 131])
                    
                    full_message = f"<{syslog_priority}>{timestamp_dt.strftime('%b %d %H:%M:%S')} {values['hostname']}: {message_content}"
                    
                    record = {
                        "message": full_message,
                        "timestamp": timestamp_dt.isoformat() + 'Z'
                    }
                    
                    f.write(json.dumps(record) + '\n')
                    
                except (KeyError, ValueError):
                    continue
        
        print(f"✅ Generated {count} FortiGate logs → {output_file.name}")
        return output_file
    
    def generate_weighted_ip(self) -> str:
        """Generate IP with realistic distribution (more internal than external)"""
        if random.random() < 0.7:  # 70% internal
            return self.generate_internal_ip()
        else:
            return self.generate_external_ip()
    
    def generate_internal_ip(self) -> str:
        """Generate internal IP address"""
        network = random.choice(self.internal_networks)
        return network + str(random.randint(1, 254))
    
    def generate_external_ip(self) -> str:
        """Generate external IP address"""
        network = random.choice(self.external_networks)
        return network + str(random.randint(1, 254))
    
    def generate_realistic_port(self, high_ports: bool = True) -> int:
        """Generate realistic port numbers"""
        if high_ports:
            # Ephemeral/high ports for source
            return random.choice(
                list(range(1024, 5000)) * 10 +  # Common ephemeral range
                list(range(32768, 65536)) * 5   # Linux ephemeral range
            )
        else:
            # Well-known ports for destination
            return random.choice([
                22, 23, 25, 53, 80, 110, 143, 443, 993, 995,  # Common services
                21, 22, 23, 25, 53, 80, 110, 443,             # Repeated common ones
                8080, 8443, 3389, 1433, 3306, 5432           # Application ports
            ])


def main():
    """Generate large syslog samples matching existing types"""
    print("🚀 Generating Large Syslog Samples")
    print("=" * 50)
    
    generator = LargeSyslogGenerator()
    
    generated_files = [
        generator.generate_cisco_asa_large(5000),
        generator.generate_cisco_ios_large(3000),
        generator.generate_fortigate_large(2000),
    ]
    
    print("\n" + "=" * 50)
    print("📊 GENERATION COMPLETE")
    print("=" * 50)
    
    total_records = 0
    for file_path in generated_files:
        if file_path.exists():
            with open(file_path, 'r') as f:
                line_count = sum(1 for _ in f)
            
            size_mb = file_path.stat().st_size / (1024 * 1024)
            total_records += line_count
            print(f"✅ {file_path.name}: {line_count:,} records ({size_mb:.1f}MB)")
    
    print(f"\n🎯 Total: {total_records:,} log records generated!")
    print("Ready for VRL testing with realistic, varied datasets")


if __name__ == "__main__":
    main()