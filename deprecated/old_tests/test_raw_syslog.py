#!/usr/bin/env python3
"""
Test token-aware context with REALISTIC raw syslog data
that requires actual VRL parsing of the msg field
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

from persistent_vrl_session import PersistentVRLSession, RequestType


def test_raw_syslog(sample_file: str, device_type: str):
    print(f"\n{'='*20} {device_type.upper()} RAW SYSLOG {'='*20}")
    
    # Initialize session with raw syslog data
    session = PersistentVRLSession(sample_file)
    
    # Get VRL creation context - this should focus on parsing the msg field
    context = session.get_llm_context_for_new_conversation(request_type=RequestType.CREATE_VRL)
    
    print(f"📊 Context Stats:")
    print(f"   Characters: {len(context):,}")
    print(f"   Estimated tokens: ~{len(context)//3.5:.0f}")
    
    # Show what the LLM will see about the msg field patterns
    print(f"\n📋 Key Context Preview (first 800 chars):")
    print(context[:800] + "...")
    
    # Get session summary to see what patterns were detected  
    summary = session.get_session_summary()
    print(f"\n🔍 Pattern Analysis:")
    print(f"   Common fields: {len(summary['sample_info']['common_fields'])}")
    print(f"   Delimiters found: {', '.join(summary['sample_info']['delimiters_found'])}")
    
    # Show first sample's msg field to see what needs parsing
    with open(sample_file, 'r') as f:
        import json
        first_sample = json.loads(f.readline())
        print(f"\n📝 Raw msg field to parse:")
        print(f"   '{first_sample.get('msg', 'NO MSG FIELD')[:100]}...'")
        print(f"   logoriginal: '{first_sample.get('logoriginal', 'NO LOGORIGINAL')[:80]}...'")
    
    return session


def main():
    print("=" * 80)
    print("TESTING RAW SYSLOG WITH TOKEN-AWARE CONTEXT")
    print("=" * 80)
    
    # Test both Cisco device types with realistic raw syslog
    test_cases = [
        ("samples/cisco-ios-raw.ndjson", "Cisco IOS"),
        ("samples/cisco-asa-raw.ndjson", "Cisco ASA")
    ]
    
    for sample_file, device_type in test_cases:
        session = test_raw_syslog(sample_file, device_type)
        
        # Show what the VRL parser needs to extract
        print(f"\n🎯 VRL Parsing Challenge for {device_type}:")
        print("   ✅ Basic syslog header already parsed (facility, severity, hostname)")
        print("   🔍 NEEDS PARSING: msg field contains the actual log content")
        print("   📋 Target extractions:")
        
        if "ios" in sample_file:
            print("      - Sequence number (000123, 000124, etc.)")
            print("      - Facility (LINEPROTO, SYS, BGP, OSPF)")
            print("      - Severity level (3, 5, 6)")
            print("      - Mnemonic (UPDOWN, CPUHOG, ADJCHANGE)")
            print("      - Interface names (GigabitEthernet0/1)")
            print("      - IP addresses and process details")
        else:  # ASA
            print("      - Message ID (%ASA-4-106023, %ASA-3-302013)")
            print("      - Action (Deny, Built)")
            print("      - Protocol (tcp, udp, icmp)")
            print("      - Source/destination zones and IPs")
            print("      - Port numbers and connection details")
    
    print(f"\n" + "=" * 80)
    print("🎯 REALISTIC SYSLOG TESTING READY")
    print("✅ Raw msg fields require actual VRL parsing")
    print("📊 Token-aware context optimized for parsing tasks")
    print("🔥 Ready for real-world VRL development!")
    print("=" * 80)


if __name__ == "__main__":
    main()