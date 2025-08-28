# CORE VRL GENERATION PROMPT (All Models)
©️ 2025 HyperSec Pty Ltd. All rights reserved.

## UNIVERSAL VRL RULES (Apply to ALL models)

### 1. VRL Language Fundamentals
- VRL is Vector Remap Language for log transformation
- Expression-based, not statement-based
- No loops, no user-defined functions
- All operations must handle errors explicitly

### 2. Critical Syntax Rules
```vrl
# CORRECT - Infallible operations with !
parts = split!(message, " ")
value = to_int!(string_value)
result = parse_json!(json_string)

# WRONG - Fallible operations without handling
parts = split(message, " ")  # ERROR: E103
```

### 3. Array Access Rules
```vrl
# CORRECT - Literal integers only
first = array[0]
second = array[1]

# WRONG - Variable indexing not supported
item = array[index_var]  # SYNTAX ERROR
```

### 4. Required Field Processing Order
1. Extract fields using string operations FIRST
2. Transform/convert data types SECOND  
3. Normalize formats (downcase, etc.) LAST
4. Add metadata at END

### 5. Performance Priorities
- String operations: 50-100x faster than regex
- Use contains!, starts_with!, ends_with! over regex
- Make operations infallible with ! when safe

### 6. Error Handling
- Use ! for guaranteed success (infallible)
- Use error tuple for conditional: `value, err = operation()`
- Never use ?? after ! (redundant)

### 7. Type Safety
```vrl
# Always coerce types before operations
msg = string!(.message)  # Ensure string type
parts = split!(msg, " ")  # Now safe to split
```

## REQUIRED OUTPUT STRUCTURE

### Header (Always include):
```vrl
# Parser for: [Data Source]
# DFE identified [N] key fields for [domain purpose]
# Performance tier: [Fast/Standard]
```

### Field Extraction Pattern:
```vrl
# Step 1: Get message and ensure type
if exists(.message) || exists(.msg) {
    msg = string!(.message ?? .msg)
    
    # Step 2: Extract fields
    # [extraction logic]
    
    # Step 3: Normalize (at end)
    if exists(.hostname) {
        .hostname = downcase!(string!(.hostname))
    }
}
```

### Metadata Addition:
```vrl
# Always add at END
.dfe_parser = "auto_generated"
.dfe_version = "1.0.0"
.dfe_timestamp = now()
```

## COMMON PATTERNS

### SSH Log Pattern:
```vrl
msg = string!(.message)
if contains!(msg, "sshd[") {
    parts = split!(msg, " ")
    if length(parts) > 6 {
        .timestamp = parts[0] + " " + parts[1]
        .hostname = downcase!(parts[2])
        .process = parts[3]
    }
}
```

### JSON Log Pattern:
```vrl
if starts_with!(string!(.message), "{") {
    .parsed = parse_json!(string!(.message))
    .hostname = downcase!(string!(.parsed.host ?? ""))
    .severity = string!(.parsed.level ?? "info")
}
```

## FORBIDDEN CONSTRUCTS
- ❌ Loops: `for`, `while`, `each`
- ❌ Custom functions: `function myFunc()`
- ❌ File I/O: `read_file()` (except enrichment tables)
- ❌ Variable array indexing: `array[variable]`
- ❌ Empty returns: `return` (use expression result)

## SUCCESS CRITERIA
1. ✅ All operations use ! or error handling
2. ✅ No E103 errors (unhandled fallible)
3. ✅ No dynamic array indexing
4. ✅ Types coerced before operations
5. ✅ Fields normalized at end
6. ✅ Metadata added last

## VALIDATION CHECKLIST
Before returning VRL, verify:
- [ ] All split() → split!()
- [ ] All parse_json() → parse_json!()  
- [ ] All to_int() → to_int!()
- [ ] All array[var] → array[0], array[1], etc.
- [ ] All .field access has string!() wrapper if needed
- [ ] No empty return statements
- [ ] No ?? after ! operations
- [ ] NO INVENTED FUNCTIONS: Only use standard VRL functions
- [ ] Type conversion: Use ONLY string!(), to_int!(), to_float!(), to_bool!()
- [ ] No string_fast!(), int32!(), or other made-up functions

## CRITICAL: VRL FUNCTION REFERENCE (ONLY USE THESE)
### Type Conversion:
- string!(value) - convert to string
- to_int!(value) - convert to integer  
- to_float!(value) - convert to float
- to_bool!(value) - convert to boolean

### String Functions:
- split!(string, delimiter) - split string (fallible)
- contains(string, pattern) - check if contains (infallible)
- starts_with(string, prefix) - check prefix (infallible)
- ends_with(string, suffix) - check suffix (infallible)
- downcase(string) - lowercase (infallible)
- upcase(string) - uppercase (infallible)
- length(string_or_array) - get length (infallible)

### Parsing Functions:
- parse_json!(json_string) - parse JSON (fallible)
- parse_timestamp!(time_string, format: "pattern") - parse time (fallible)

### DO NOT INVENT FUNCTIONS LIKE:
❌ string_fast!(), string_low_cardinality!()
❌ int32!(), int64!(), float64!()
❌ ip_address!(), hostname!(), url!()

These don't exist in VRL. Use the standard functions above.