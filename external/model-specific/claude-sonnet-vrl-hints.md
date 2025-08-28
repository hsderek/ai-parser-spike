# Claude Sonnet Specific VRL Hints

## Claude Sonnet 3.5 Characteristics

Claude Sonnet is more efficient but still has some VRL quirks:

### 1. Better with ! Operator
Sonnet usually remembers the ! operator better than Opus, but still misses it occasionally:
```vrl
# Sonnet usually gets this right:
parts = split!(msg, " ")

# But sometimes forgets on less common functions:
timestamp = parse_timestamp(date_str)  # WRONG
timestamp = parse_timestamp!(date_str) # CORRECT
```

### 2. Unnecessary Error Coalescing
Sonnet sometimes adds ?? to infallible operations:
```vrl
# WRONG (Sonnet does this):
value = to_int!(str) ?? 0

# CORRECT (! already makes it infallible):
value = to_int!(str)
```

### 3. More Concise Code
Sonnet generates more compact VRL, which is good, but watch for:
- Missing null checks
- Assumptions about field existence

## Best Practices for Claude Sonnet:
1. Remind about ! for parse_timestamp, parse_regex
2. No need for ?? after ! operations
3. Encourage explicit null checks
4. Leverage Sonnet's efficiency for simpler patterns

## Example for Sonnet:
```vrl
# Claude Sonnet optimal pattern
.parsed = parse_json!(string!(.message))
.hostname = downcase!(.parsed.host ?? "unknown")
.severity = .parsed.level ?? "info"
.timestamp = parse_timestamp!(.parsed.time, format: "%Y-%m-%d %H:%M:%S")
```