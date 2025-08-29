# GPT Model Specific VRL Hints

## Common GPT-4/GPT-5 VRL Issues

GPT models often confuse VRL with Python or JavaScript syntax:

### 1. Python-like Function Names
GPT uses Python builtins instead of VRL functions:
```vrl
# WRONG (GPT does this):
text = str(value)
num = int(string_val)
parts = value.split(" ")

# CORRECT VRL:
text = to_string!(value)
num = to_int!(string_val)
parts = split!(value, " ")
```

### 2. Method Syntax Instead of Functions
GPT uses OOP method calls:
```vrl
# WRONG:
result = message.toLowerCase()
parts = text.split(",")
length = array.length()

# CORRECT:
result = downcase!(message)
parts = split!(text, ",")
length = length(array)
```

### 3. JavaScript/Python Patterns
```vrl
# WRONG (GPT patterns):
for item in items:  # No loops in VRL!
if (condition) {    # No parentheses needed

# CORRECT:
# Use conditional logic instead of loops
if condition {
```

## Must-Correct for GPT Models:
1. Replace Python builtins: str→to_string!, int→to_int!
2. Convert method syntax to functions
3. Remove loop constructs
4. Fix regex syntax (VRL uses r'pattern')
5. Add ! to all operations

## GPT Correction Example:
```vrl
# What GPT generates:
msg = str(event.message)
parts = msg.split(" ")
for i in range(len(parts)):
    process(parts[i])

# Corrected for VRL:
msg = to_string!(event.message)
parts = split!(msg, " ")
# Process specific indices instead of loop
if length(parts) > 0 {
    .field1 = parts[0]
}
if length(parts) > 1 {
    .field2 = parts[1]
}
```