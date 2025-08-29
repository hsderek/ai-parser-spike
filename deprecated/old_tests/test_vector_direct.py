#!/usr/bin/env python3
"""
Direct Vector test - minimal dependencies
Tests VRL with actual Vector and outputs to samples-parsed/
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path
import shutil


def test_vector_direct():
    """Test Vector directly without all the framework dependencies"""
    
    print("=" * 60)
    print("Testing Cisco IOS parsing with actual Vector")
    print("=" * 60)
    
    sample_file = Path("samples/cisco-ios.ndjson")
    parsed_dir = Path("samples-parsed")
    parsed_dir.mkdir(exist_ok=True)
    
    # VRL code for Cisco IOS parsing
    vrl_code = """
# Cisco IOS VRL Parser
# Extract fields from Cisco IOS syslog messages

# Normalize hostname to lowercase snake_case
if exists(.hostname) {
    .hostname_normalized = downcase(string!(.hostname))
}

# Parse severity to human-readable label
if exists(.severity) {
    severity_num = to_int(.severity) ?? 6
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
    pri_value = to_int(.priority) ?? 0
    .facility_num = floor(pri_value / 8)
    .severity_num = mod(pri_value, 8)
}

# Parse Cisco IOS specific patterns from message
if exists(.msg) {
    msg = string!(.msg)
    
    # Extract IOS facility, severity, and mnemonic
    # Pattern: %FACILITY-SEVERITY-MNEMONIC:
    ios_match = parse_regex(msg, r'%(?P<facility>[A-Z]+)-(?P<severity>\\d+)-(?P<mnemonic>[A-Z_]+):') ?? {}
    
    if length(ios_match) > 0 {
        .ios_facility = ios_match.facility ?? null
        .ios_severity = ios_match.severity ?? null
        .ios_mnemonic = ios_match.mnemonic ?? null
    }
}

# Normalize timestamp
if exists(.timestamp) {
    .timestamp_normalized = string!(.timestamp)
}

# Add processing metadata
._parser_metadata = {
    "parser_version": "1.0.0",
    "parser_type": "cisco_ios",
    "processed_by": "vector_vrl",
    "processed_at": now()
}

# Return the event
.
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy input file
        temp_input = temp_path / "input.ndjson"
        shutil.copy(sample_file, temp_input)
        
        # Write VRL file
        vrl_file = temp_path / "transform.vrl"
        with open(vrl_file, 'w') as f:
            f.write(vrl_code)
        
        # Create Vector YAML config
        output_file = temp_path / "output.ndjson"
        config_file = temp_path / "vector.yaml"
        
        config = f"""
# Vector configuration for Cisco IOS parsing
sources:
  cisco_ios_input:
    type: file
    include:
      - "{temp_input}"
    read_from: beginning
    encoding:
      codec: json

transforms:
  cisco_ios_parser:
    type: remap
    inputs:
      - cisco_ios_input
    file: "{vrl_file}"
    drop_on_error: false
    drop_on_abort: false

sinks:
  parsed_output:
    type: file
    inputs:
      - cisco_ios_parser
    path: "{output_file}"
    encoding:
      codec: ndjson
"""
        
        with open(config_file, 'w') as f:
            f.write(config)
        
        print(f"Config file: {config_file}")
        print(f"VRL file: {vrl_file}")
        print(f"Input: {temp_input}")
        print(f"Output: {output_file}")
        
        # First validate the configuration
        print("\nValidating Vector configuration...")
        validate_cmd = ["vector", "validate", str(config_file)]
        result = subprocess.run(validate_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Configuration validation failed!")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False
        
        print("✅ Configuration is valid")
        
        # Run Vector
        print("\nRunning Vector to process logs...")
        run_cmd = ["vector", "--quiet", str(config_file)]
        
        process = subprocess.Popen(
            run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give Vector time to process
        print("Processing...")
        time.sleep(3)
        
        # Terminate Vector
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        # Check if output was created
        if not output_file.exists():
            print(f"❌ No output file created")
            print(f"stderr: {stderr[:500]}")
            return False
        
        # Read the parsed output
        parsed_records = []
        with open(output_file, 'r') as f:
            for line in f:
                if line.strip():
                    parsed_records.append(json.loads(line))
        
        if not parsed_records:
            print("❌ No records in output file")
            return False
        
        print(f"✅ Processed {len(parsed_records)} records")
        
        # Save to samples-parsed directory
        
        # 1. Save parsed data
        final_output = parsed_dir / "cisco-ios-parsed.ndjson"
        with open(final_output, 'w') as f:
            for record in parsed_records:
                f.write(json.dumps(record) + '\n')
        print(f"✅ Saved parsed data to {final_output}")
        
        # 2. Save VRL code
        final_vrl = parsed_dir / "cisco-ios.vrl"
        with open(final_vrl, 'w') as f:
            f.write(vrl_code)
        print(f"✅ Saved VRL code to {final_vrl}")
        
        # 3. Save metadata
        # Load original for comparison
        original_records = []
        with open(sample_file, 'r') as f:
            for line in f:
                if line.strip():
                    original_records.append(json.loads(line))
        
        original_fields = set(original_records[0].keys()) if original_records else set()
        parsed_fields = set(parsed_records[0].keys()) if parsed_records else set()
        new_fields = parsed_fields - original_fields
        
        metadata = {
            "source_file": str(sample_file),
            "output_file": str(final_output),
            "vrl_file": str(final_vrl),
            "vector_version": "0.49.0",
            "records_processed": len(parsed_records),
            "original_fields": sorted(list(original_fields)),
            "new_fields_added": sorted(list(new_fields)),
            "total_fields": len(parsed_fields),
            "parser_info": {
                "type": "cisco_ios_vrl",
                "method": "vector_processing"
            }
        }
        
        final_metadata = parsed_dir / "cisco-ios-result.json"
        with open(final_metadata, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Saved metadata to {final_metadata}")
        
        # Show sample of new fields
        print("\n📊 New fields added by Vector:")
        first_record = parsed_records[0]
        for field in sorted(new_fields):
            if field in first_record:
                value = first_record[field]
                if isinstance(value, dict):
                    print(f"  {field}: <dict>")
                else:
                    print(f"  {field}: {value}")
        
        print(f"\n✅ SUCCESS! All files saved to samples-parsed/")
        return True


if __name__ == "__main__":
    import sys
    success = test_vector_direct()
    sys.exit(0 if success else 1)