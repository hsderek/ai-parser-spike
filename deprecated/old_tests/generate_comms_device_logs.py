#!/usr/bin/env python3
"""
Generate realistic communications device syslog samples based on real format patterns

Creates syslog samples from network devices like Cisco switches/routers, Juniper, 
Meraki, and other communications equipment using actual syslog format patterns.
"""

import json
import random
import datetime
import hashlib
from typing import List, Dict, Any

class CommsDeviceLogGenerator:
    """Generate realistic communications device syslog samples"""
    
    def __init__(self):
        self.start_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        
        # Real device hostnames
        self.devices = {
            'cisco_switches': ['sw-core-01', 'sw-dist-01', 'sw-access-01', 'sw-access-02'],
            'cisco_routers': ['rtr-edge-01', 'rtr-edge-02', 'rtr-wan-01'],
            'juniper': ['jun-srx-01', 'jun-ex4300-01', 'jun-mx480-01'],
            'meraki': ['MX84-01', 'MS220-8P-01', 'MR18-01'],
            'arista': ['arista-7050-01', 'arista-7280-01'],
            'palo_alto': ['pa-5220-01', 'pa-850-01']
        }
        
        # Real interface names
        self.interfaces = [
            'GigabitEthernet0/1', 'GigabitEthernet1/0/1', 'FastEthernet0/1',
            'ge-0/0/0', 'xe-0/1/0', 'et-0/0/0', 'Ethernet1', 'Ethernet1/1'
        ]
        
        # Real IP addresses (RFC1918 and documentation ranges)
        self.internal_ips = [
            '10.1.1.1', '10.1.1.254', '10.10.10.1', '10.20.30.40',
            '192.168.1.1', '192.168.1.254', '192.168.100.1',
            '172.16.1.1', '172.16.10.1', '172.31.255.254'
        ]
        
        self.external_ips = [
            '8.8.8.8', '8.8.4.4', '1.1.1.1', '208.67.222.222',
            '198.51.100.1', '203.0.113.1', '198.18.0.1'
        ]
    
    def generate_timestamp(self) -> datetime.datetime:
        """Generate incrementing timestamp"""
        self.start_time += datetime.timedelta(seconds=random.randint(1, 60))
        return self.start_time
    
    def create_dfe_log(self, message: str, hostname: str, source_type: str, 
                      severity: str = 'info', facility: int = 16) -> Dict[str, Any]:
        """Create DFE schema log entry for communications devices"""
        timestamp = self.generate_timestamp()
        timestamp_str = timestamp.isoformat() + 'Z'
        
        severity_map = {
            'emergency': '0', 'alert': '1', 'critical': '2', 'error': '3',
            'warning': '4', 'notice': '5', 'info': '6', 'debug': '7'
        }
        
        severity_num = severity_map.get(severity.lower(), '6')
        priority = facility * 8 + int(severity_num)
        
        event_hash = hashlib.md5(f"{timestamp_str}{message}".encode()).hexdigest()
        
        return {
            "@timestamp": timestamp_str,
            "event_hash": event_hash,
            "facility": str(facility),
            "facility_label": "local0" if facility == 16 else f"facility{facility}",
            "hostname": hostname,
            "logoriginal": f"<{priority}>{timestamp.strftime('%b %d %Y %H:%M:%S')}: {hostname}: {message}",
            "logsource": hostname,
            "msg": message,
            "message": message,
            "org_id": "enterprise",
            "port": 514,
            "priority": str(priority),
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
                    "source": "network",
                    "timestamp": timestamp_str,
                    "timezone": "UTC"
                },
                "event": {
                    "category": f"logs_network_{source_type}",
                    "org_id": "enterprise",
                    "site_id": "datacenter",
                    "type": f"event.network.{source_type}"
                },
                "replayed": False
            },
            "timestamp": timestamp_str,
            "timestamp_epochms": int(timestamp.timestamp() * 1000),
            "timestamp_finalise": (timestamp + datetime.timedelta(seconds=1)).isoformat() + 'Z',
            "timestamp_load": (timestamp + datetime.timedelta(seconds=2)).isoformat() + 'Z',
            "timestamp_received": timestamp_str,
            "timestamp_received_epochms": int(timestamp.timestamp() * 1000)
        }
    
    def generate_cisco_ios_logs(self, count: int = 500) -> List[Dict[str, Any]]:
        """Generate Cisco IOS switch/router logs based on real patterns"""
        samples = []
        
        # Real Cisco IOS syslog message patterns
        cisco_patterns = [
            # Interface state changes
            lambda: f"%LINEPROTO-5-UPDOWN: Line protocol on Interface {random.choice(self.interfaces)}, changed state to {'up' if random.random() > 0.3 else 'down'}",
            lambda: f"%LINK-3-UPDOWN: Interface {random.choice(self.interfaces)}, changed state to {'up' if random.random() > 0.5 else 'down'}",
            
            # Spanning tree
            lambda: f"%SPANTREE-2-ROOTGUARD_CONFIG_CHANGE: Root guard is now {'enabled' if random.random() > 0.5 else 'disabled'} on port {random.choice(self.interfaces)}",
            lambda: f"%SPANTREE-2-BLOCK_BPDUGUARD: Received BPDU on port {random.choice(self.interfaces)} with BPDU Guard enabled. Disabling port.",
            
            # CDP/LLDP
            lambda: f"%CDP-4-DUPLEX_MISMATCH: duplex mismatch discovered on {random.choice(self.interfaces)} (not {'full' if random.random() > 0.5 else 'half'} duplex), with {random.choice(self.devices['cisco_switches'])} {random.choice(self.interfaces)} ({'full' if random.random() > 0.5 else 'half'} duplex).",
            
            # Security
            lambda: f"%SEC-6-IPACCESSLOGP: list {random.randint(100,199)} {'denied' if random.random() > 0.3 else 'permitted'} tcp {random.choice(self.external_ips)}({random.randint(1024,65535)}) -> {random.choice(self.internal_ips)}({random.choice([22,23,80,443,3389])}), {random.randint(1,100)} packet",
            lambda: f"%SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: admin] [Source: {random.choice(self.internal_ips)}] [localport: 22] at {datetime.datetime.now().strftime('%H:%M:%S')} UTC",
            lambda: f"%SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: {random.choice(['admin', 'root', 'user1'])}] [Source: {random.choice(self.external_ips)}] [localport: 22] [Reason: Invalid password] at {datetime.datetime.now().strftime('%H:%M:%S')} UTC",
            
            # OSPF/BGP
            lambda: f"%OSPF-5-ADJCHG: Process 1, Nbr {random.choice(self.internal_ips)} on {random.choice(self.interfaces)} from {'FULL to DOWN' if random.random() > 0.7 else 'LOADING to FULL'}, Neighbor Down: {'Dead timer expired' if random.random() > 0.5 else 'Interface down or detached'}",
            lambda: f"%BGP-5-ADJCHANGE: neighbor {random.choice(self.external_ips)} {'Up' if random.random() > 0.5 else 'Down'} {'BGP Notification sent' if random.random() > 0.5 else ''}",
            
            # DHCP
            lambda: f"%DHCPD-4-DECLINE_CONFLICT: DHCP address conflict: client {f'01{random.randint(10,99)}.{random.randint(1000,9999)}.{random.randint(1000,9999)}'} declined {random.choice(self.internal_ips)}.",
            lambda: f"%DHCPD-4-PING_CONFLICT: DHCP address conflict: server pinged {random.choice(self.internal_ips)}.",
            
            # Hardware
            lambda: f"%PLATFORM-3-ELEMENT_WARNING: {random.choice(['Temperature', 'Power Supply', 'Fan'])} {random.randint(1,4)} is {'above normal' if random.random() > 0.5 else 'operating normally'}",
            lambda: f"%PLATFORM_ENV-1-FAN: Fan {random.randint(1,4)} had a rotation error reported.",
            
            # STP
            lambda: f"%SW_MATM-4-MACFLAP_NOTIF: Host {f'{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}'} in vlan {random.randint(1,4094)} is flapping between port {random.choice(self.interfaces)} and port {random.choice(self.interfaces)}",
            
            # Configuration
            lambda: f"%SYS-5-CONFIG_I: Configured from console by admin on vty0 ({random.choice(self.internal_ips)})",
            lambda: f"%PARSER-5-CFGLOG_LOGGEDCMD: User:admin  logged command:{'interface ' + random.choice(self.interfaces) if random.random() > 0.5 else 'no shutdown'}",
        ]
        
        for _ in range(count):
            hostname = random.choice(self.devices['cisco_switches'] + self.devices['cisco_routers'])
            message = random.choice(cisco_patterns)()
            
            # Determine severity from message
            severity = 'info'
            if '%-1-' in message or '%-0-' in message:
                severity = 'critical'
            elif '%-2-' in message:
                severity = 'alert'
            elif '%-3-' in message:
                severity = 'error'
            elif '%-4-' in message:
                severity = 'warning'
            elif '%-5-' in message:
                severity = 'notice'
                
            log_entry = self.create_dfe_log(message, hostname, 'cisco_ios', severity)
            samples.append(log_entry)
            
        return samples
    
    def generate_juniper_logs(self, count: int = 300) -> List[Dict[str, Any]]:
        """Generate Juniper Junos logs based on real patterns"""
        samples = []
        
        # Real Juniper syslog patterns
        juniper_patterns = [
            # Interface events
            lambda: f"mib2d[{random.randint(1000,9999)}]: SNMP_TRAP_LINK_{'UP' if random.random() > 0.3 else 'DOWN'}: ifIndex {random.randint(100,999)}, ifAdminStatus {'up' if random.random() > 0.5 else 'down'}, ifOperStatus {'up' if random.random() > 0.5 else 'down'}, ifName {random.choice(['ge-0/0/0', 'xe-0/1/0', 'et-0/0/0'])}",
            
            # Security events
            lambda: f"RT_FLOW: RT_FLOW_SESSION_{'CREATE' if random.random() > 0.3 else 'CLOSE'} session created {random.choice(self.internal_ips)}/{random.randint(1024,65535)}->{random.choice(self.external_ips)}/{random.choice([80,443,22,25])} {random.choice(['junos-http', 'junos-https', 'junos-ssh', 'junos-smtp'])} {random.choice(self.internal_ips)}/{random.randint(1024,65535)}->{random.choice(self.external_ips)}/{random.choice([80,443,22,25])} None None {random.randint(1,100)} {'allow' if random.random() > 0.2 else 'deny'} trust untrust {random.randint(100000,999999)}",
            
            # Firewall
            lambda: f"PFE_FW_SYSLOG_IP: FW: {random.choice(['ge-0/0/0', 'xe-0/1/0'])}.0 {'A' if random.random() > 0.5 else 'D'} {random.choice(['tcp', 'udp', 'icmp'])} {random.choice(self.external_ips)} {random.choice(self.internal_ips)} {random.randint(1,65535)} {random.randint(1,65535)}",
            
            # Routing
            lambda: f"rpd[{random.randint(1000,9999)}]: BGP_PREFIX_THRESH_EXCEEDED: {random.choice(self.external_ips)} (External AS {random.randint(1,65535)}): Configured maximum prefix-limit({random.randint(1000,10000)}) exceeded for inet-unicast nlri: {random.randint(10001,20000)} (instance master)",
            lambda: f"rpd[{random.randint(1000,9999)}]: OSPF neighbor {random.choice(self.internal_ips)} (realm ospf-v2 {random.choice(['ge-0/0/0', 'xe-0/1/0'])}.0 area 0.0.0.0) state changed from {'Full to Init' if random.random() > 0.7 else 'Init to Full'} due to {'1WayRcvd' if random.random() > 0.5 else '2WayRcvd'}",
            
            # System
            lambda: f"mgd[{random.randint(1000,9999)}]: UI_{'COMMIT' if random.random() > 0.3 else 'ROLLBACK'}: User 'admin' performed {'commit' if random.random() > 0.3 else 'rollback'}",
            lambda: f"sshd[{random.randint(10000,99999)}]: {'Accepted' if random.random() > 0.3 else 'Failed'} password for admin from {random.choice(self.internal_ips)} port {random.randint(10000,65535)} ssh2",
            
            # Hardware
            lambda: f"chassisd[{random.randint(1000,9999)}]: CHASSISD_SNMP_TRAP10: SNMP trap generated: {'Temperature' if random.random() > 0.5 else 'Power'} sensor {random.choice(['FPC 0', 'Routing Engine', 'CB 0'])} {'OK' if random.random() > 0.7 else 'Warm'}",
            
            # VPN
            lambda: f"kmd[{random.randint(1000,9999)}]: IKE negotiation {'completed' if random.random() > 0.6 else 'failed'} for local: {random.choice(self.internal_ips)}, remote: {random.choice(self.external_ips)} IKEv2 with status: {'Established' if random.random() > 0.6 else 'No proposal chosen'}",
        ]
        
        for _ in range(count):
            hostname = random.choice(self.devices['juniper'])
            message = random.choice(juniper_patterns)()
            
            # Determine severity from content
            severity = 'info'
            if 'failed' in message.lower() or 'exceeded' in message.lower():
                severity = 'warning'
            elif 'error' in message.lower():
                severity = 'error'
            elif 'down' in message.lower():
                severity = 'notice'
                
            log_entry = self.create_dfe_log(message, hostname, 'juniper', severity)
            samples.append(log_entry)
            
        return samples
    
    def generate_meraki_logs(self, count: int = 200) -> List[Dict[str, Any]]:
        """Generate Cisco Meraki logs based on real patterns"""
        samples = []
        
        # Real Meraki syslog patterns based on documentation
        meraki_patterns = [
            # Security appliance (MX)
            lambda: f"firewall src={random.choice(self.internal_ips)} dst={random.choice(self.external_ips)} mac={f'{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}'} protocol={'tcp' if random.random() > 0.3 else 'udp'} sport={random.randint(1024,65535)} dport={random.choice([80,443,22,53,25])}",
            lambda: f"events type=vpn_connectivity_change vpn_type='site-to-site' peer_contact='{random.choice(self.external_ips)}:{random.randint(500,51856)}'",
            lambda: f"flows {'allow' if random.random() > 0.2 else 'deny'} src={random.choice(self.internal_ips)} dst={random.choice(self.external_ips)} mac={f'{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}'} protocol={'tcp' if random.random() > 0.3 else 'udp'} sport={random.randint(1024,65535)} dport={random.choice([80,443,22,53])}",
            lambda: f"urls src={random.choice(self.internal_ips)}:{random.randint(1024,65535)} dst={random.choice(self.external_ips)}:{random.choice([80,443])} mac={f'{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}'} request: {'GET' if random.random() > 0.3 else 'POST'} {random.choice(['example.com', 'google.com', 'microsoft.com', 'amazon.com'])}",
            
            # Switch (MS)
            lambda: f"events port {random.randint(1,48)} status changed from {'100fdx' if random.random() > 0.5 else '1000fdx'} to {'down' if random.random() > 0.7 else 'up'}",
            lambda: f"events type=8021x_auth port='{random.randint(1,48)}' identity='{random.choice(['user', 'admin', 'employee'])}@example.com'",
            lambda: f"events dhcp lease of ip {random.choice(self.internal_ips)} from server {random.choice(['10.1.1.1', '192.168.1.1'])} for client mac {f'{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}'} on subnet {random.choice(['10.1.1.0/24', '192.168.1.0/24'])} with dns {random.choice(['8.8.8.8', '1.1.1.1'])}",
            
            # Wireless (MR)
            lambda: f"events type={'association' if random.random() > 0.3 else 'disassociation'} radio='{random.randint(0,1)}' vap='{random.randint(0,3)}' channel='{random.choice([1,6,11,36,40,44,48])}' rssi='{random.randint(15,40)}'",
            lambda: f"events type=wpa_auth radio='{random.randint(0,1)}' vap='{random.randint(0,3)}' client_mac='{f'{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}'}'",
            lambda: f"events type={'rogue_ap_detected' if random.random() > 0.8 else 'interference'} channel='{random.choice([1,6,11])}' rssi='{random.randint(10,50)}'",
        ]
        
        for _ in range(count):
            device_type = random.choice(['MX84', 'MS220_8P', 'MR18'])
            hostname = f"{device_type}-{random.choice(['01', '02', '03'])}"
            
            # Generate timestamp for Meraki format
            timestamp = self.generate_timestamp()
            meraki_timestamp = f"{int(timestamp.timestamp())}.{random.randint(100000000,999999999)}"
            
            message_pattern = random.choice(meraki_patterns)()
            message = f"{meraki_timestamp} {hostname} {message_pattern}"
            
            severity = 'info'
            if 'deny' in message or 'disassociation' in message:
                severity = 'notice'
            elif 'rogue' in message:
                severity = 'warning'
            elif 'down' in message:
                severity = 'warning'
                
            log_entry = self.create_dfe_log(message, hostname, 'meraki', severity)
            samples.append(log_entry)
            
        return samples

def main():
    """Generate communications device syslog samples"""
    generator = CommsDeviceLogGenerator()
    
    print("=" * 80)
    print("GENERATING COMMUNICATIONS DEVICE SYSLOG SAMPLES")
    print("=" * 80)
    
    total_samples = 0
    
    # Generate Cisco IOS logs
    print("\n📡 Generating Cisco IOS switch/router logs...")
    cisco_samples = generator.generate_cisco_ios_logs(500)
    with open('samples/large/cisco-ios-real.ndjson', 'w') as f:
        for sample in cisco_samples:
            f.write(json.dumps(sample) + '\n')
    print(f"   ✅ Generated {len(cisco_samples)} Cisco IOS log samples")
    total_samples += len(cisco_samples)
    
    # Generate Juniper logs
    print("\n📡 Generating Juniper Junos logs...")
    generator.start_time = datetime.datetime.now() - datetime.timedelta(hours=24)
    juniper_samples = generator.generate_juniper_logs(300)
    with open('samples/large/juniper-real.ndjson', 'w') as f:
        for sample in juniper_samples:
            f.write(json.dumps(sample) + '\n')
    print(f"   ✅ Generated {len(juniper_samples)} Juniper log samples")
    total_samples += len(juniper_samples)
    
    # Generate Meraki logs
    print("\n📡 Generating Cisco Meraki logs...")
    generator.start_time = datetime.datetime.now() - datetime.timedelta(hours=24)
    meraki_samples = generator.generate_meraki_logs(200)
    with open('samples/large/meraki-real.ndjson', 'w') as f:
        for sample in meraki_samples:
            f.write(json.dumps(sample) + '\n')
    print(f"   ✅ Generated {len(meraki_samples)} Meraki log samples")
    total_samples += len(meraki_samples)
    
    print("\n" + "=" * 80)
    print(f"✅ GENERATION COMPLETE")
    print(f"   Total samples generated: {total_samples:,}")
    print(f"   Communications devices covered:")
    print(f"     - Cisco IOS switches/routers: 500 samples")
    print(f"     - Juniper Junos devices: 300 samples")
    print(f"     - Cisco Meraki (MX/MS/MR): 200 samples")
    print(f"   Files saved to: samples/large/")
    print("=" * 80)

if __name__ == "__main__":
    main()