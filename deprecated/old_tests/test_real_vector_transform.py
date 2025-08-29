#!/usr/bin/env python3
"""
Test real Vector CLI transformation with raw syslog data
Shows actual before/after JSON transformation
"""

import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

from vrl_testing_loop_clean import VRLTestingLoop


def main():
    print("=" * 80)
    print("REAL VECTOR CLI TRANSFORMATION TEST")
    print("=" * 80)
    
    # Clean previous results
    import subprocess
    subprocess.run(["rm", "-f", "samples-parsed/*"], shell=True)
    
    # Initialize VRL testing loop with LARGE Cisco ASA data
    loop = VRLTestingLoop("samples/cisco-asa-large.ndjson")
    
    print("\n📋 Testing realistic Cisco ASA VRL with Vector CLI...")
    print("🎯 Goal: Parse raw msg field into structured data")
    
    # Show the BEFORE state - raw input
    print("\n" + "="*60)
    print("BEFORE - Raw Syslog Input")
    print("="*60)
    
    with open("samples/cisco-asa-raw.ndjson", 'r') as f:
        raw_sample = json.loads(f.readline())
    
    print("Raw input sample (what VRL receives):")
    print(json.dumps(raw_sample, indent=2))
    
    print(f"\n🔍 Key field to parse:")
    print(f"message: '{raw_sample['message']}'")
    print(f"Length: {len(raw_sample['message'])} chars")
    print(f"Contains: Syslog header + ASA message ID, action, protocol, IPs, ports, ACL")
    
    # Create a realistic VRL that parses Cisco ASA messages
    cisco_asa_vrl = """
# Cisco ASA VRL Parser - Real-world message field parsing
. = parse_json!(string!(.message))

# Parse the message field for syslog + ASA-specific data
if exists(.message) {
    msg_content = string!(.message)
    
    # First extract syslog header info
    if starts_with(msg_content, "<") {
        # Extract priority from <NNN>
        priority_end = index(msg_content, ">")!
        if priority_end > 1 {
            priority_str = slice(msg_content, 1, priority_end)!
            .syslog_priority = to_int!(priority_str)
            .syslog_facility = to_int!(priority_str) / 8
            .syslog_severity = to_int!(priority_str) % 8
            
            # Get the rest after priority
            msg_content = slice(msg_content, priority_end + 1, -1)!
        }
    }
    
    # Extract hostname (after timestamp, before colon)
    if contains(msg_content, ":") {
        time_host_parts = split(msg_content, ":", 2)
        if length(time_host_parts) >= 2 {
            # Extract hostname from the datetime part
            datetime_host = strip_whitespace(time_host_parts[0])!
            host_parts = split(datetime_host, " ")
            if length(host_parts) > 0 {
                .syslog_hostname = string!(host_parts[-1])
            }
            
            # Get ASA message content (everything after first colon)
            asa_content = join(slice(time_host_parts, 1, -1)!, ":")
            msg_content = asa_content
        }
    }
    
    # Extract ASA message ID (%ASA-X-XXXXXX)
    if contains(msg_content, "%ASA-") {
        # Split on %ASA- to get message parts
        asa_parts = split(msg_content, "%ASA-")
        if length(asa_parts) > 1 {
            # Get severity-messagecode part (e.g., "4-106023")
            severity_code_part = split(asa_parts[1], ":")
            if length(severity_code_part) > 0 {
                severity_code = severity_code_part[0]
                severity_parts = split(severity_code, "-")
                if length(severity_parts) == 2 {
                    .asa_severity_level = string!(severity_parts[0])
                    .asa_message_code = string!(severity_parts[1])
                    .asa_message_id = "%ASA-" + severity_code
                }
            }
        }
    }
    
    # Extract action (Deny, Allow, Built, etc.)
    if contains(msg_content, "Deny ") {
        .asa_action = "Deny"
    } else if contains(msg_content, "Built ") {
        .asa_action = "Built"  
    } else if contains(msg_content, "Allow ") {
        .asa_action = "Allow"
    }
    
    # Extract protocol
    if contains(msg_content, " tcp ") {
        .asa_protocol = "tcp"
    } else if contains(msg_content, " udp ") {
        .asa_protocol = "udp"
    } else if contains(msg_content, " icmp ") {
        .asa_protocol = "icmp"
    }
    
    # Extract source information (src zone:ip/port)
    if contains(msg_content, "src ") {
        src_parts = split(msg_content, "src ")
        if length(src_parts) > 1 {
            # Get the part after "src " up to " dst"
            src_info = split(src_parts[1], " dst")[0]
            if contains(src_info, ":") {
                zone_ip_parts = split(src_info, ":")
                if length(zone_ip_parts) == 2 {
                    .asa_src_zone = string!(zone_ip_parts[0])
                    # Split IP and port
                    if contains(zone_ip_parts[1], "/") {
                        ip_port = split(zone_ip_parts[1], "/")
                        if length(ip_port) == 2 {
                            .asa_src_ip = string!(ip_port[0])
                            .asa_src_port = string!(ip_port[1])
                        }
                    } else {
                        .asa_src_ip = string!(zone_ip_parts[1])
                    }
                }
            }
        }
    }
    
    # Extract destination information (dst zone:ip/port)
    if contains(msg_content, "dst ") {
        dst_parts = split(msg_content, "dst ")
        if length(dst_parts) > 1 {
            # Get the part after "dst " up to next space or end
            dst_info = split(dst_parts[1], " ")[0]
            if contains(dst_info, ":") {
                zone_ip_parts = split(dst_info, ":")
                if length(zone_ip_parts) == 2 {
                    .asa_dst_zone = string!(zone_ip_parts[0])
                    # Split IP and port  
                    if contains(zone_ip_parts[1], "/") {
                        ip_port = split(zone_ip_parts[1], "/")
                        if length(ip_port) == 2 {
                            .asa_dst_ip = string!(ip_port[0])
                            .asa_dst_port = string!(ip_port[1])
                        }
                    } else {
                        .asa_dst_ip = string!(zone_ip_parts[1])
                    }
                }
            }
        }
    }
    
    # Extract ACL name
    if contains(msg_content, "access-group ") {
        acl_parts = split(msg_content, "access-group ")
        if length(acl_parts) > 1 {
            # Get ACL name between quotes or until space
            acl_part = acl_parts[1]
            if contains(acl_part, "\"") {
                acl_quoted = split(acl_part, "\"")
                if length(acl_quoted) > 1 {
                    .asa_acl_name = string!(acl_quoted[1])
                }
            }
        }
    }
}

# Add parser metadata
._parser_metadata = {
    "parser_version": "1.0.0",
    "parser_type": "cisco_asa_firewall",
    "strategy": "string_operations_msg_parsing",
    "timestamp": now()
}

# Return the enriched event
.
"""
    
    print(f"\n📄 VRL Code to test ({len(cisco_asa_vrl)} chars):")
    print("Uses contains(), split(), string ops (NO REGEX)")
    print("Extracts: syslog header (priority, facility, severity, hostname)")
    print("         + ASA: message_id, action, protocol, src/dst zones/IPs/ports, ACL")
    
    # Run the VRL testing loop with Vector CLI
    success = loop.run_with_llm_generated_vrl(cisco_asa_vrl, 1)
    
    if success:
        print(f"\n✅ Vector CLI transformation completed!")
        
        # Show the AFTER state - transformed output
        print(f"\n" + "="*60)
        print("AFTER - Vector CLI Transformed Output")
        print("="*60)
        
        # Read the actual Vector-generated output
        output_file = Path("samples-parsed/cisco-asa-raw.json")
        if output_file.exists():
            with open(output_file, 'r') as f:
                # Vector outputs NDJSON, get first line
                transformed_sample = json.loads(f.readline())
            
            print("Transformed output (actual Vector CLI result):")
            print(json.dumps(transformed_sample, indent=2))
            
            # Show the key differences
            print(f"\n🔥 NEW FIELDS EXTRACTED BY VRL:")
            new_fields = []
            for key, value in transformed_sample.items():
                if key.startswith('asa_') or key.startswith('syslog_') or key == '_parser_metadata':
                    new_fields.append(f"  {key}: {value}")
            
            if new_fields:
                print('\n'.join(new_fields))
            else:
                print("  (No new syslog/ASA fields found - check VRL parsing)")
                
            print(f"\n📊 Transformation Stats:")
            print(f"  Original fields: {len(raw_sample)}")
            print(f"  Final fields: {len(transformed_sample)}")
            print(f"  New fields added: {len(transformed_sample) - len(raw_sample)}")
            
        else:
            print("❌ No Vector output file found!")
            print(f"Expected: {output_file}")
            
    else:
        print(f"\n❌ VRL transformation failed!")
        if loop.candidates:
            latest = loop.candidates[-1]
            print(f"Errors: {', '.join(latest.errors)}")
    
    print(f"\n" + "=" * 80)
    print("REAL VECTOR CLI TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()