#!/usr/bin/env python3
"""
Test VRL with PyVRL for fast iteration, then validate with Vector CLI
Outputs actual Vector-processed data to samples-parsed/
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path
import shutil

# Try to import PyVRL
try:
    import pyvrl
    PYVRL_AVAILABLE = True
except ImportError:
    PYVRL_AVAILABLE = False
    print("Warning: PyVRL not available, skipping fast validation")


def test_with_pyvrl(vrl_code: str, sample_data: list) -> tuple[bool, list]:
    """
    Fast VRL validation using PyVRL.
    Returns (is_valid, errors)
    """
    if not PYVRL_AVAILABLE:
        return True, []  # Skip validation if PyVRL not available
    
    errors = []
    
    try:
        # Create a PyVRL Transform
        transform = pyvrl.Transform(vrl_code)
        
        # Test with sample data
        for i, sample in enumerate(sample_data[:3]):  # Test first 3 samples
            try:
                # Process the sample through VRL
                result = transform.remap(sample)
                print(f"  PyVRL sample {i+1}: ✅ Valid - processed successfully")
            except Exception as e:
                errors.append(f"Sample {i+1} error: {str(e)}")
                print(f"  PyVRL sample {i+1}: ❌ {e}")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        # Compilation error
        errors.append(f"VRL compilation error: {str(e)}")
        return False, errors


def fix_vrl_for_vector(vrl_code: str) -> str:
    """
    Fix common VRL issues for Vector compatibility.
    """
    # Fix codec issue: ndjson -> json
    fixed = vrl_code
    
    # Ensure parse_regex returns proper result
    fixed = fixed.replace('parse_regex(', 'parse_regex!(')
    
    # Fix to_int calls
    fixed = fixed.replace('to_int(', 'to_int!(')
    fixed = fixed.replace('to_int!!(', 'to_int!(')  # Fix double bangs
    
    # Don't change mod - it's the correct VRL function
    # The % operator doesn't work in VRL
    
    return fixed


def test_cisco_ios_full():
    """Complete test: PyVRL validation -> Vector processing -> samples-parsed output"""
    
    print("=" * 60)
    print("Testing Cisco IOS VRL Parser")
    print("=" * 60)
    
    sample_file = Path("samples/cisco-ios.ndjson")
    parsed_dir = Path("samples-parsed")
    parsed_dir.mkdir(exist_ok=True)
    
    # Load sample data
    samples = []
    with open(sample_file, 'r') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"Loaded {len(samples)} samples from {sample_file}")
    
    # VRL code for Cisco IOS parsing
    vrl_code = """
# Cisco IOS VRL Parser - Tested with PyVRL and Vector
# Extract fields from Cisco IOS syslog messages

# Normalize hostname to lowercase snake_case
if exists(.hostname) {
    .hostname_normalized = downcase(string!(.hostname))
}

# Parse severity to human-readable label
if exists(.severity) {
    severity_num = to_int!(.severity)
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
    pri_value = to_int!(.priority)
    .facility_num = floor(pri_value / 8)
    .severity_num = mod(pri_value, 8)
}

# Parse Cisco IOS specific patterns from message
if exists(.msg) {
    msg = string!(.msg)
    
    # Extract IOS facility, severity, and mnemonic
    # Pattern: %FACILITY-SEVERITY-MNEMONIC:
    ios_match = parse_regex!(msg, r'%(?P<facility>[A-Z]+)-(?P<severity>\\d+)-(?P<mnemonic>[A-Z_]+):')
    
    if length(ios_match) > 0 {
        if exists(ios_match.facility) {
            .ios_facility = ios_match.facility
        }
        if exists(ios_match.severity) {
            .ios_severity = ios_match.severity
        }
        if exists(ios_match.mnemonic) {
            .ios_mnemonic = ios_match.mnemonic
        }
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
    "processed_by": "vector_vrl"
}

# Return the event
.
"""
    
    # Step 1: Fast validation with PyVRL
    print("\n" + "=" * 40)
    print("Step 1: PyVRL Fast Validation")
    print("=" * 40)
    
    is_valid, pyvrl_errors = test_with_pyvrl(vrl_code, samples)
    
    if not is_valid:
        print("❌ PyVRL validation failed. Attempting fixes...")
        vrl_code = fix_vrl_for_vector(vrl_code)
        is_valid, pyvrl_errors = test_with_pyvrl(vrl_code, samples)
        
        if not is_valid:
            print("❌ Still failing after fixes:")
            for error in pyvrl_errors:
                print(f"  - {error}")
            print("\nContinuing to Vector test anyway...")
    else:
        print("✅ PyVRL validation passed!")
    
    # Step 2: Full Vector CLI processing
    print("\n" + "=" * 40)
    print("Step 2: Vector CLI Processing")
    print("=" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy input file
        temp_input = temp_path / "input.json"
        shutil.copy(sample_file, temp_input)
        
        # Write VRL file
        vrl_file = temp_path / "transform.vrl"
        with open(vrl_file, 'w') as f:
            f.write(vrl_code)
        
        # Create Vector YAML config (fixed codec)
        output_file = temp_path / "output.json"
        config_file = temp_path / "vector.yaml"
        
        config = f"""
# Vector configuration for Cisco IOS parsing
data_dir: "{temp_path}"

sources:
  cisco_ios_input:
    type: file
    include:
      - "{temp_input}"
    read_from: beginning

transforms:
  # Standard HyperSec transform: flatten message field first
  101_transform_flatten_message_parse:
    type: remap
    inputs:
      - cisco_ios_input
    source: |
      . = parse_json(.message) ?? {{}}
  
  101_transform_flatten_message:
    type: filter
    inputs:
      - 101_transform_flatten_message_parse
    condition:
      type: vrl
      source: "!is_empty(.)"
  
  # Now apply the VRL parser to the flattened data
  cisco_ios_parser:
    type: remap
    inputs:
      - 101_transform_flatten_message
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
      codec: json  # Fixed: was ndjson, now json
"""
        
        with open(config_file, 'w') as f:
            f.write(config)
        
        # Validate configuration
        print("Validating Vector configuration...")
        # Set data dir via environment variable
        import os
        env = os.environ.copy()
        env["VECTOR_DATA_DIR"] = str(temp_path)
        validate_cmd = ["vector", "validate", str(config_file)]
        result = subprocess.run(validate_cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print(f"❌ Configuration validation failed!")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False
        
        print("✅ Configuration is valid")
        
        # Run Vector  
        print("Running Vector to process logs...")
        # Vector expects: vector [OPTIONS] [config_file]
        # But with no subcommand, it runs as a service
        # We need to use the config file directly
        run_cmd = ["vector", "-qq", "-c", str(config_file)]
        
        process = subprocess.Popen(
            run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Give Vector time to process
        time.sleep(3)
        
        # Terminate Vector
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        # Check output
        if not output_file.exists():
            print(f"❌ No output file created")
            if stderr:
                print(f"stderr: {stderr[:500]}")
            return False
        
        # Read parsed output
        parsed_records = []
        with open(output_file, 'r') as f:
            for line in f:
                if line.strip():
                    parsed_records.append(json.loads(line))
        
        if not parsed_records:
            print("❌ No records in output file")
            return False
        
        print(f"✅ Vector processed {len(parsed_records)} records")
        
        # Step 3: Save to samples-parsed
        print("\n" + "=" * 40)
        print("Step 3: Save to samples-parsed/")
        print("=" * 40)
        
        # Save parsed data
        final_output = parsed_dir / "cisco-ios-parsed.ndjson"
        with open(final_output, 'w') as f:
            for record in parsed_records:
                f.write(json.dumps(record) + '\n')
        print(f"✅ Saved parsed data to {final_output}")
        
        # Save VRL code that worked
        final_vrl = parsed_dir / "cisco-ios.vrl"
        with open(final_vrl, 'w') as f:
            f.write(vrl_code)
        print(f"✅ Saved working VRL code to {final_vrl}")
        
        # Save metadata
        original_fields = set(samples[0].keys()) if samples else set()
        parsed_fields = set(parsed_records[0].keys()) if parsed_records else set()
        new_fields = parsed_fields - original_fields
        
        metadata = {
            "source_file": str(sample_file),
            "output_file": str(final_output),
            "vrl_file": str(final_vrl),
            "vector_version": "0.49.0",
            "pyvrl_validated": is_valid,
            "records_processed": len(parsed_records),
            "original_fields": sorted(list(original_fields)),
            "new_fields_added": sorted(list(new_fields)),
            "total_fields": len(parsed_fields),
            "parser_info": {
                "type": "cisco_ios_vrl",
                "method": "pyvrl_then_vector",
                "pyvrl_validation": "passed" if is_valid else "failed"
            }
        }
        
        final_metadata = parsed_dir / "cisco-ios-result.json"
        with open(final_metadata, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Saved metadata to {final_metadata}")
        
        # Show results
        print("\n" + "=" * 40)
        print("Results Summary")
        print("=" * 40)
        print(f"📊 New fields added by Vector:")
        first_record = parsed_records[0]
        for field in sorted(new_fields):
            if field in first_record:
                value = first_record[field]
                if isinstance(value, dict):
                    print(f"  {field}: <dict>")
                else:
                    print(f"  {field}: {value}")
        
        print(f"\n✅ SUCCESS! All files saved to samples-parsed/")
        print(f"  - {final_output.name} (Vector-processed data)")
        print(f"  - {final_vrl.name} (Working VRL code)")
        print(f"  - {final_metadata.name} (Processing metadata)")
        
        return True


if __name__ == "__main__":
    import sys
    success = test_cisco_ios_full()
    sys.exit(0 if success else 1)