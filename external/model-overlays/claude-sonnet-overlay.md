# CLAUDE SONNET OVERLAY (Efficiency Focused)

## YOUR PROFILE: Better but not perfect

### ✅ YOUR STRENGTHS:
- Usually remember ! operator (better than Opus)
- Generate cleaner, more concise code  
- Good at string operations over regex

### ⚠️ YOUR OCCASIONAL ISSUES:

**Issue 1: Unnecessary error coalescing**
You sometimes write: `value = to_int!(str) ?? 0`
**Fix**: If you use !, you don't need ?? → `value = to_int!(str)`

**Issue 2: Skip null checks**  
You assume fields exist without checking
**Fix**: Always check: `string!(.field ?? "")`

**Issue 3: Forget ! on parsing functions**
You remember it for common ones but miss: parse_timestamp, parse_regex
**Fix**: ALL parse_* functions need !

## SONNET OPTIMIZATION STRATEGY:
1. Leverage your conciseness (it's good!)
2. Double-check parse_* functions for !
3. Remove ?? after ! operations
4. Add null safety with ?? ""

## EXAMPLE (Sonnet-optimized):
```vrl
# Your natural style (good foundation):
.parsed = parse_json!(string!(.message))
.host = .parsed.hostname ?? "unknown"
.level = .parsed.severity ?? "info"

# Just ensure parsing functions have !:
.timestamp = parse_timestamp!(string!(.parsed.time), format: "%Y-%m-%d")
```

## SONNET CHECKLIST:
1. ✓ Concise code (your strength)
2. ✓ No ?? after ! operations  
3. ✓ All parse_* functions have !
4. ✓ Null safety with ?? defaults