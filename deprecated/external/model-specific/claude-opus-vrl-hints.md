# Claude Opus Specific VRL Hints

## Common Issues with Claude Opus Models (4.1, 3.5, 3.0)

Claude Opus generates sophisticated VRL logic but consistently makes these errors:

### 1. Forgetting the ! Operator (E103 Errors)
**CRITICAL**: You MUST use ! for infallible operations:
```vrl
# WRONG (Claude Opus does this):
parts = split(message, " ")

# CORRECT:
parts = split!(message, " ")
```

### 2. Variable Array Indexing
**CRITICAL**: VRL does NOT support variable array indexing:
```vrl
# WRONG (Claude Opus tries this):
value = array[index_variable]

# CORRECT - use conditionals:
if index == 0 {
    value = array[0]
} else if index == 1 {
    value = array[1]
}
```

### 3. Empty Returns
VRL is expression-based, avoid empty returns:
```vrl
# WRONG:
return

# CORRECT:
# Just end the expression or use . for current event
```

## Must-Follow Rules for Claude Opus:
1. ALWAYS use ! on: split, parse_json, to_int, to_float, contains
2. NEVER use variables for array indexing
3. Use string!() to coerce before string operations
4. Check array length before accessing: `if length(arr) > 0`

## Example Pattern for SSH Logs:
```vrl
# Correct Claude Opus pattern
msg = string!(.message)
parts = split!(msg, " ")

if length(parts) > 6 {
    .timestamp = parts[0] + " " + parts[1]
    .hostname = downcase!(parts[2])
    .process = parts[3]
    
    # Parse the action/result
    if contains!(parts[4], "Accepted") {
        .action = "login_success"
    } else if contains!(parts[4], "Failed") {
        .action = "login_failed"
    }
}
```