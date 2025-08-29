#!/usr/bin/env python3
"""
Test VRL parsing with actual Vector - no simulation!
Generates samples-parsed output from real Vector processing.
"""
import json
from pathlib import Path
import sys
sys.path.append('.')

from src.vector_pipeline import VectorPipeline
from src.logging_config import setup_logging


def test_cisco_ios_with_vector():
    """Test cisco-ios parsing with actual Vector"""
    
    # Setup logging
    setup_logging(
        log_level='INFO',
        log_to_file=False,
        log_to_console=True,
        logs_dir='./logs',
        app_name='vector_test',
        structured_logging=False,
        debug_mode=False
    )
    
    print("=" * 60)
    print("Testing Cisco IOS parsing with actual Vector")
    print("=" * 60)
    
    sample_file = Path("samples/cisco-ios.ndjson")
    
    # Example VRL code for Cisco IOS parsing
    # This should normally come from the LLM generation
    vrl_code = """
# Cisco IOS VRL Parser
# Extract fields from Cisco IOS syslog messages

# Extract hostname (already present, just normalize)
if exists(.hostname) {
    .hostname_normalized = downcase!(string!(.hostname))
}

# Parse severity to label
if exists(.severity) {
    severity_num = to_int!(.severity) ?? 6
    .severity_label = if severity_num == 0 {
        "emergency"
    } else if severity_num == 1 {
        "alert"
    } else if severity_num == 2 {
        "critical"
    } else if severity_num == 3 {
        "error"
    } else if severity_num == 4 {
        "warning"
    } else if severity_num == 5 {
        "notice"
    } else if severity_num == 6 {
        "info"
    } else {
        "debug"
    }
}

# Extract facility and severity from priority
if exists(.priority) {
    pri_value = to_int!(.priority) ?? 0
    .facility_num = pri_value / 8
    .severity_num = pri_value % 8
}

# Parse Cisco IOS specific patterns from message
if exists(.msg) {
    msg = string!(.msg)
    
    # Extract IOS facility, severity, and mnemonic
    # Pattern: %FACILITY-SEVERITY-MNEMONIC:
    ios_pattern = parse_regex!(msg, r'%(?P<facility>[A-Z]+)-(?P<severity>\\d+)-(?P<mnemonic>[A-Z_]+):') ?? {}
    
    if exists(ios_pattern.facility) {
        .ios_facility = ios_pattern.facility
    }
    if exists(ios_pattern.severity) {
        .ios_severity = ios_pattern.severity
    }
    if exists(ios_pattern.mnemonic) {
        .ios_mnemonic = ios_pattern.mnemonic
    }
}

# Normalize timestamp
if exists(.timestamp) {
    .timestamp_normalized = string!(.timestamp)
}

# Add parser metadata
._parser_metadata = {
    "parser_version": "1.0.0",
    "parser_type": "cisco_ios",
    "processed_by": "vector_vrl"
}

# Return the modified event
.
"""
    
    # Create pipeline
    pipeline = VectorPipeline()
    
    # Mock parser metadata (normally from LLM result)
    parser_metadata = {
        "narrative": "Cisco IOS syslog parser using HyperSec DFE patterns",
        "fields": [
            {"name": "hostname_normalized", "type": "string"},
            {"name": "severity_label", "type": "string"},
            {"name": "facility_num", "type": "int"},
            {"name": "severity_num", "type": "int"},
            {"name": "ios_facility", "type": "string"},
            {"name": "ios_severity", "type": "string"},
            {"name": "ios_mnemonic", "type": "string"},
            {"name": "timestamp_normalized", "type": "string"}
        ]
    }
    
    # Process with Vector
    success = pipeline.process_with_vrl(
        sample_file,
        vrl_code,
        parser_metadata
    )
    
    if success:
        print("\n✅ SUCCESS! Check samples-parsed/ for output:")
        parsed_dir = Path("samples-parsed")
        for file in parsed_dir.glob("cisco-ios*"):
            print(f"  - {file.name}")
        
        # Show a sample of the parsed output
        parsed_file = parsed_dir / "cisco-ios-parsed.ndjson"
        if parsed_file.exists():
            print("\nSample parsed record:")
            with open(parsed_file, 'r') as f:
                first_line = f.readline()
                if first_line:
                    record = json.loads(first_line)
                    # Show new fields
                    new_fields = [
                        "hostname_normalized",
                        "severity_label",
                        "facility_num",
                        "severity_num",
                        "ios_facility",
                        "ios_severity",
                        "ios_mnemonic",
                        "timestamp_normalized",
                        "_parser_metadata"
                    ]
                    print("  New fields added by Vector:")
                    for field in new_fields:
                        if field in record:
                            value = record[field]
                            if isinstance(value, dict):
                                print(f"    {field}: <dict>")
                            else:
                                print(f"    {field}: {value}")
    else:
        print("\n❌ FAILED! Vector processing failed.")
        print("Check that Vector is properly installed and the VRL code is valid.")
    
    return success


if __name__ == "__main__":
    success = test_cisco_ios_with_vector()
    sys.exit(0 if success else 1)