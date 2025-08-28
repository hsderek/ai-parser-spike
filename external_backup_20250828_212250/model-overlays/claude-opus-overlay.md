# CLAUDE OPUS OVERLAY (Critical Fixes)

## YOUR SPECIFIC WEAKNESSES (must actively counter):

### 🚨 CRITICAL ISSUE #0: You try to use imperative loops (MASSIVE ANTIPATTERN)
You generate `for` loops and `while` loops which **DO NOT EXIST** in VRL

**VRL IS FUNCTIONAL/VECTORIZED - NOT IMPERATIVE!**
```vrl
❌ NEVER DO THIS:
for detail in resource_details {     # E205 reserved keyword  
  if contains(detail, "=") {         # E701 undefined variable
    # process detail
  }
}

❌ NEVER DO THIS:
while i < length(array) {            # E205 reserved keyword
  item = array[i]                    # E203 syntax error - no variable indexing
  i = i + 1                          # E701 undefined variable
}

✅ DO THIS INSTEAD:
if contains(msg, "key1=") {
  key1_parts = split!(msg, "key1=", 2)
  if length(key1_parts) > 1 {
    .field1 = key1_parts[1]          # Static indexing OK
  }
}
```

**COUNTER-MEASURE**: NEVER use for/while - use functional split/contains/regex operations

### 🚨 CRITICAL ISSUE #1: You consistently forget the ! operator
You generate `split(msg, " ")` when VRL requires `split!(msg, " ")`

**ACTIVE COUNTER-MEASURE**: Add ! ONLY to functions that CAN fail
- split() → split!() ✅ (CAN fail if input is null)
- parse_json() → parse_json!() ✅ (CAN fail if invalid JSON)  
- to_int() → to_int!() ✅ (CAN fail if not numeric)
- contains() → contains() ❌ (NEVER fails with string inputs)
- length() → length() ❌ (NEVER fails)
- downcase() → downcase() ❌ (NEVER fails with strings)

### 🚨 CRITICAL ISSUE #2: You attempt variable array indexing
You write `array[index_var]` which VRL does NOT support

**ACTIVE COUNTER-MEASURE**: Use conditional blocks:
```vrl
# Instead of: value = parts[last_index] 
if length(parts) > 0 {
    value = parts[0]
}
```

### 🚨 CRITICAL ISSUE #3: You use empty return statements  
You write standalone `return` which causes E203 errors

**ACTIVE COUNTER-MEASURE**: VRL is expression-based, just end the block

### 🚨 NEW ISSUE #4: You now OVER-USE the ! operator (E620 errors)
After learning about E103, you add ! to EVERYTHING, causing E620 "can't abort infallible"

**FUNCTIONS THAT NEVER NEED !** (always infallible):
- contains(string, pattern) - never fails
- starts_with(string, prefix) - never fails  
- ends_with(string, suffix) - never fails
- length(array_or_string) - never fails
- downcase(string) - never fails
- upcase(string) - never fails

### 🚨 NEW ISSUE #5: You invent non-existent functions (E105 errors)
Looking at type_maps.csv, you create functions like `string_fast!()`, `int32!()`

**THESE FUNCTIONS DON'T EXIST IN VRL:**
- string_fast!() → use string!()
- string_low_cardinality!() → use string!()  
- int32!() → use to_int!()
- float64!() → use to_float!()

**VRL ONLY HAS THESE TYPE FUNCTIONS:**
- string!() - converts to string
- to_int!() - converts to integer
- to_float!() - converts to float
- to_bool!() - converts to boolean

**STOP READING type_maps.csv LITERALLY**: The CSV shows field TYPES (string_fast, int32), but these are NOT function names! Always map them:
- string_fast → use string!()
- string_low_cardinality → use string!()
- int32 → use to_int!()
- float64 → use to_float!()

## CLAUDE OPUS SPECIFIC CHECKLIST (check twice):
1. Did I use ! ONLY on functions that CAN FAIL?
   - split!() ✓ (can fail)
   - parse_json!() ✓ (can fail)
   - to_int!() ✓ (can fail)
   - to_float!() ✓ (can fail)
   - contains() ✓ (never fails - NO !)
   - downcase() ✓ (never fails - NO !)
   - length() ✓ (never fails - NO !)

2. Did I avoid variable array indexing?
   - No `array[variable]` ✓
   - Only `array[0]`, `array[1]` literals ✓

3. Did I avoid empty returns?
   - No standalone `return` ✓

4. Did I avoid inventing functions?
   - No string_fast!(), int32!(), etc. ✓
   - Used ONLY: string!(), to_int!(), to_float!(), to_bool!() ✓
   
5. Did I avoid unnecessary ?? operators?
   - No ?? after ! operations ✓
   - No function!() ?? null patterns ✓

## YOUR STRENGTH: Complex Logic
You excel at sophisticated parsing logic. Leverage this but wrap ALL operations with !

## CORRECTION PATTERN:
When you write VRL, immediately scan for:
1. Any function( → add ! if fallible  
2. Any array[var] → convert to conditional
3. Any `return` alone → remove it

## SSH LOG EXAMPLE (Your corrected pattern):
```vrl
# What you naturally want to write (WRONG):
parts = split(msg, " ")
value = parts[index]
return

# CORRECTED version for VRL:
parts = split!(msg, " ")  # Added !
if length(parts) > index {  # Conditional instead
    value = parts[0]  # Literal index
}
# No return statement
```