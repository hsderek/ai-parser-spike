#!/usr/bin/env python3
"""
Test field naming convention normalization
"""
from src.field_naming import (
    normalize_field_name,
    FieldNamingConvention,
    standardize_field_name,
    FIELD_NAME_ALIASES
)


def test_field_naming():
    """Test various field name transformations"""
    
    test_cases = [
        # Original field names from various sources
        ("@timestamp", "timestamp"),
        ("eventTime", "event_time"),
        ("DateTime", "date_time"),
        ("userName", "user_name"),
        ("UserName", "user_name"),
        ("user-name", "user_name"),
        ("user.name", "user_name"),
        ("srcIP", "src_ip"),
        ("src_ip", "src_ip"),  # Already snake_case
        ("source-ip-address", "source_ip_address"),
        ("HTTPStatusCode", "http_status_code"),
        ("IOSFacility", "ios_facility"),
        ("CPUUsagePercent", "cpu_usage_percent"),
        ("hostName", "host_name"),
        ("log.level", "log_level"),
        ("error_message", "error_message"),  # Already snake_case
        ("ErrorMessage", "error_message"),
        ("error-message", "error_message"),
        ("UPPERCASE_FIELD", "uppercase_field"),
        ("mixedCase_with_Underscores", "mixed_case_with_underscores"),
    ]
    
    print("Testing SNAKE_CASE conversion (default):")
    print("-" * 50)
    
    for original, expected in test_cases:
        result = normalize_field_name(original, FieldNamingConvention.SNAKE_CASE)
        status = "✅" if result == expected else "❌"
        print(f"{status} {original:30} -> {result:30} (expected: {expected})")
    
    print("\n\nTesting other conventions:")
    print("-" * 50)
    
    test_field = "HTTPStatusCode"
    conventions = [
        (FieldNamingConvention.SNAKE_CASE, "http_status_code"),
        (FieldNamingConvention.CAMEL_CASE, "httpStatusCode"),
        (FieldNamingConvention.PASCAL_CASE, "HttpStatusCode"),
        (FieldNamingConvention.KEBAB_CASE, "http-status-code"),
        (FieldNamingConvention.ORIGINAL, "HTTPStatusCode"),
    ]
    
    for convention, expected in conventions:
        result = normalize_field_name(test_field, convention)
        status = "✅" if result == expected else "❌"
        print(f"{status} {test_field} -> {convention.value:15} -> {result:20} (expected: {expected})")
    
    print("\n\nTesting field aliases:")
    print("-" * 50)
    
    for original, standardized in list(FIELD_NAME_ALIASES.items())[:10]:
        result = standardize_field_name(original)
        status = "✅" if result == standardized else "❌"
        print(f"{status} {original:20} -> {result:20} (expected: {standardized})")
    
    print("\n\nTesting special character preservation:")
    print("-" * 50)
    
    special_fields = [
        ("@timestamp", True, "@timestamp"),  # Preserve @
        ("@timestamp", False, "timestamp"),  # Don't preserve @
        (".hidden", True, ".hidden"),        # Preserve .
        (".hidden", False, "hidden"),        # Don't preserve .
        ("_internal", True, "_internal"),    # Preserve _
        ("_internal", False, "internal"),    # Don't preserve _
    ]
    
    for original, preserve, expected in special_fields:
        result = normalize_field_name(
            original, 
            FieldNamingConvention.SNAKE_CASE,
            preserve_special_chars=preserve
        )
        status = "✅" if result == expected else "❌"
        preserve_str = "preserve" if preserve else "strip"
        print(f"{status} {original:15} ({preserve_str:8}) -> {result:20} (expected: {expected})")
    
    print("\n✅ Field naming convention tests complete!")
    
    # Test with actual syslog fields
    print("\n\nTesting with actual syslog fields:")
    print("-" * 50)
    
    syslog_fields = [
        "syslog.facility",
        "syslog.mnemonic",
        "syslog.severity",
        "relayip_enrich",
        "timestamp_epochms",
        "IOSSequence",
        "PaloAltoAction",
        "FortiGate_srcip",
        "pfSense-filterlog",
    ]
    
    print("Original -> snake_case:")
    for field in syslog_fields:
        result = normalize_field_name(field, FieldNamingConvention.SNAKE_CASE)
        print(f"  {field:25} -> {result}")


if __name__ == "__main__":
    test_field_naming()