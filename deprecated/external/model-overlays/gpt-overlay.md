# GPT MODELS OVERLAY (Syntax Translation)

## YOUR PROFILE: Python/JS mindset needs VRL translation

### 🚨 CRITICAL TRANSLATION NEEDED:

**Python Builtins → VRL Functions:**
- `str(value)` → `to_string!(value)`
- `int(value)` → `to_int!(value)`  
- `float(value)` → `to_float!(value)`
- `len(array)` → `length(array)`

**Method Syntax → Function Syntax:**
- `text.split(" ")` → `split!(text, " ")`
- `text.lower()` → `downcase!(text)`
- `text.upper()` → `upcase!(text)`
- `text.strip()` → `strip_whitespace!(text)`

**JavaScript Patterns → VRL:**
- `substring(start, end)` → `slice!(text, start, end)`
- `indexOf(needle)` → `find!(text, needle)`

### ❌ FORBIDDEN PATTERNS (you naturally try):
```javascript
// NO - This is JS/Python, not VRL
for (let i = 0; i < array.length; i++) {
    process(array[i])
}

if (condition) {  // No parentheses needed
```

### ✅ VRL EQUIVALENT:
```vrl
# Process array elements individually
if length(array) > 0 {
    .first = array[0] 
}
if length(array) > 1 {
    .second = array[1]
}

if condition {  # No parentheses
```

## GPT ACTIVE TRANSLATION CHECKLIST:
1. Scan for Python builtins → replace with VRL functions
2. Scan for method calls → convert to function calls  
3. Remove all loops → use conditional logic
4. Remove parentheses from if statements
5. Add ! to ALL function calls

## GPT CORRECTION EXAMPLE:
```python
# What you naturally write (Python style):
msg = str(event.message)
parts = msg.split(" ")
if len(parts) > 2:
    host = parts[1].lower()

# VRL translation:
msg = to_string!(event.message)  # str → to_string!
parts = split!(msg, " ")         # method → function
if length(parts) > 2 {           # len → length, no ()
    host = downcase!(parts[1])   # .lower → downcase!
}
```

## REMEMBER: VRL is NOT Python/JavaScript
Think functional, not object-oriented. Every operation is a function call with !.