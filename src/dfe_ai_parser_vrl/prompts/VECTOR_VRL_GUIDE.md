# Derek's Vector VRL Guide
Version: **4.2.0** · Date: **2025-08-30**

> Scope: This guide covers **VRL (Vector Remap Language) in Vector.dev only**. It excludes any non-Vector VRL dialects or features (e.g., **no UDFs**). Use this doc to teach developers how to write fast, correct VRL — and to guide LLMs. **All Vector config examples are YAML.**

---

## Table of Contents
- [1. What VRL Is (Vector-only)](#1-what-vrl-is-vector-only)
- [2. HyperSec DFE defaults — message unbundling](#2-hypersec-dfe-defaults--message-unbundling)
- [3. Quickstart Primer (YAML + VRL)](#3-quickstart-primer-yaml--vrl)
- [4. Core Semantics](#4-core-semantics)
- [5. Error Handling (Mandatory) — Patterns & Examples](#5-error-handling-mandatory--patterns--examples)
- [6. Field Access & Mutation](#6-field-access--mutation)
- [7. Strings & Parsing (JSON, timestamps)](#7-strings--parsing-json-timestamps)
- [8. Branching & Classification Patterns](#8-branching--classification-patterns)
- [9. Iteration (map/for_each) & Object Walking](#9-iteration-mapfor_each--object-walking)
- [10. Nulls, Existence & Defaults](#10-nulls-existence--defaults)
- [11. Types & Conversions](#11-types--conversions)
- [12. Merging, Renaming, Restructuring](#12-merging-renaming-restructuring)
- [13. Early Exits, Guard Clauses & Performance](#13-early-exits-guard-clauses--performance)
- [14. Performance Guide — BAD / AVOID / GOOD + Cheap Ops](#14-performance-guide--bad--avoid--good--cheap-ops)
- [15. Multi-Transform Architecture Patterns (YAML)](#15-multi-transform-architecture-patterns-yaml)
- [16. Metrics Caveats](#16-metrics-caveats)
- [17. Testing VRL (YAML tests)](#17-testing-vrl-yaml-tests)
- [18. Advice for Python & Java Developers](#18-advice-for-python--java-developers)
- [19. HyperSec DFE Integration Guide](#19-hypersec-dfe-integration-guide)
- [20. Appendix: Mini Cheatsheet](#20-appendix-mini-cheatsheet)
- [21. LLM Generation Checklist & Anti-Hallucination Notes](#21-llm-generation-checklist--anti-hallucination-notes)

---

## 1) What VRL Is (Vector-only)
- **VRL is a safe, strongly-checked, expression DSL with functional characteristics.**
- **Domain-specific**: Transform a **single event** inside Vector transforms (`remap`, `filter`, `route`, etc.).
- **Expression-oriented**: Every line is an expression; assignments mutate the current event `.`.
- **Compiled & fast**: Implemented in Rust; no VM/GC.
- **No UDFs**: You cannot define custom functions; use built-ins and include files.
- **No external I/O**: VRL cannot call HTTP, read files, or persist state.

**Hello VRL:**
```vrl
.hello = "world"
.count = to_int!(.count_str)  # aborts on invalid int
```

---

## 2) Quickstart Primer (YAML + VRL)
**A simple normaliser in YAML using VRL:**
```yaml
transforms:
  normalize:
    type: remap
    inputs: [in]
    source: |
      m = string!(.message)        # cache once if still needed
      if starts_with(m, "user=") {
        parts = split(m, " ")
        kv = {}
        for_each(parts) -> |i, p| {
          pair = split(p, "=")
          if length(pair) > 1 { kv[pair[0]] = pair[1] }
        }
        . = merge(., kv)
      }
```

**External file include (reuse code):**
```yaml
transforms:
  common:
    type: remap
    file: vrl/common.vrl
```

---

## 4) Core Semantics
- Current event is `.` (object/array/primitive).
- Assign: `.field = expr` (mutates event).
- Delete: `del(.field)` returns deleted value.
- Ternary: `cond ? a : b`.
- Closures: `-> |args| { body }` with `map`, `for_each`, `map_keys`, `map_values`.
- Abort: `abort` ends script; behaviour depends on transform settings (`drop_on_abort`).

**Examples:**
```vrl
# Replace root with parsed JSON (careful: discards other fields)
. = parse_json!(.message)

# Nested if (VRL idiomatic; no `else if` keyword)
if .code >= 500 { .level = "error" } else { if .code >= 400 { .level = "warn" } else { .level = "info" } }

# Emit N events: set `.` to an array of objects
. = [ { "line": 1 }, { "line": 2 }, { "line": 3 } ]
```

---

## 5) Error Handling (Mandatory) — Patterns & Examples
VRL enforces handling for **fallible** functions.

### 5.0) Common VRL Error Codes & Fixes
Critical error patterns learned from AI VRL generation:

• **E110 - Type mismatch**: Use type-safe variables (see 5.8)
• **E103 - Unhandled fallible**: Add `?? default` or use `!` 
• **E651 - Unnecessary coalescing**: Remove `??` from infallible operations
• **E203 - Syntax errors**: Check braces, avoid bare `return` statements
• **E701 - Undefined variable**: Ensure variables are defined before use

### 5.1 Bang form — fail fast
```vrl
. = parse_json!(.message)         # aborts on error
.user_id = to_int!(.user_id_str)  # aborts on invalid number
```

### 5.2 Safe parse with default (`??`)
```vrl
obj = parse_json(.message) ?? {}
. = merge(., obj)
lat = to_float(.lat) ?? 0.0
```

### 5.3 Capture result + error
```vrl
val, err = parse_timestamp(.ts, "%+")  # RFC3339 flex
if err != null {
  log("bad ts: " + to_string(err), level: "warn")
} else {
  .ts_parsed = val
}
```

### 5.4 Mix strategies
```vrl
# Accept non-JSON; but if we *expect* duration, fail
obj = parse_json(.message) ?? {}
. = merge(., obj)
.duration_s = parse_duration!(.duration, "s")
```

### 5.5 Guard before calling fallible fn
```vrl
if exists(.bytes) && is_string(.bytes) {
  .bytes_n = to_int!(.bytes)
}
```

### 5.6 Coalesce common types
```vrl
.user    = (.user ?? .username ?? "unknown")
.retries = (to_int(.retries) ?? 0)
```

### 5.7 Assert during tests & debug
```vrl
assert!(exists(.request_id))
assert_eq!(.status, 200)
```

---

## 5.8) Mandatory Type Safety (Prevents E110 Errors)
**CRITICAL**: VRL fields can have type `any` which causes E110 errors in string operations.

### Type Safety Pattern (Use Before ANY String Operation)
```vrl
# BEFORE any contains(), split(), starts_with(), ends_with():
field_str = if exists(.field) { to_string(.field) ?? "" } else { "" }

# THEN use field_str for ALL string operations:
if contains(field_str, "pattern") { ... }     # ✅ CORRECT
if starts_with(field_str, "prefix") { ... }   # ✅ CORRECT  
parts = split(field_str, " ")                 # ✅ CORRECT (no ?? needed)
```

### ❌ E110 Error Patterns (NEVER DO)
```vrl
if contains(.field, "pattern") { ... }       # E110: .field has type 'any'
parts = split(.message, " ") ?? []           # E110: .message has type 'any'
```

### ✅ Correct Approach
```vrl
# Handle multiple common message fields
message_str = if exists(.message) { to_string(.message) ?? "" } else { "" }
msg_str = if exists(.msg) { to_string(.msg) ?? "" } else { "" }
primary_message = if message_str != "" { message_str } else { msg_str }

# Use primary_message for all operations (E110-safe)
if contains(primary_message, "error") {
    .event_type = "error"  # ✅ Output field
}
# primary_message is NOT saved to output ✅
```

**Cost**: Type conversion ~47ns per operation (negligible vs regex at 50,000ns+)

---

## 6) Field Access & Mutation
### 6.1 Reading/writing nested
```vrl
.client.ip = .headers.remote_addr
.region     = get(.labels, ["aws", "region"]) ?? "unknown"
```

### 6.2 Deleting & renaming
```vrl
.name = del(.user.name)   # rename user.name -> name
```
```vrl
tmp = del(.old_field)
.new_field = tmp
```

### 6.3 Copy vs move
```vrl
.copy = .source               # copy (keep original)
.moved = del(.source)         # move (delete original)
```

### 6.4 Replace root safely
```vrl
obj = parse_json(.message) ?? {}
. = merge(., obj)             # keep existing fields
```

### 6.5 Create nested when missing
```vrl
if !exists(.tags) { .tags = {} }
.tags.env = (.tags.env ?? "prod")
```

---

## 7) Strings & Parsing (JSON, timestamps)
> **HyperSec policy:** **NEVER use regex** in VRL. Prefer built-in `parse_*` or simple splits/anchors.

### 7.1 Cache hot strings (once!)
```vrl
m = string!(.message)
```

### 7.2 Anchored checks
```vrl
if starts_with(m, "GET ") { .method = "GET" }
if ends_with(m, " OK")    { .ok = true }
```

### 7.3 Contains (when needed)
```vrl
if contains(m, "error") { .level = "error" }
```

### 7.4 Split once, reuse
```vrl
parts = split(m, " ")
.method = parts[0]
.path   = parts[1] ?? "/"
```

### 7.5 JSON parse (replace vs enrich)
```vrl
. = parse_json!(m)               # replace
```
```vrl
obj = parse_json(m) ?? {}
. = merge(., obj)                # enrich
```

### 7.6 Timestamp parsing
```vrl
.ts = parse_timestamp!(.time, "%+")      # RFC3339/ISO-8601
```

### 7.7 Key/value parsing
```vrl
# status=200 duration=2.5s ok=true
kv = {}
for_each(split(m, " ")) -> |i, p| {
  pair = split(p, "=")
  if length(pair) > 1 { kv[pair[0]] = pair[1] }
}
. = merge(., kv)
.status   = to_int(.status) ?? null
.duration = parse_duration(.duration, "s") ?? null
```

### 7.8 URL & query (simple)
```vrl
# naive path & query split
p = split(.url ?? "", "?")
.path  = p[0] ?? ""
.query = (length(p) > 1 ? p[1] : "")
```

---

## 8) Branching & Classification Patterns

### 8.0 Performance: Nested Common Conditions  
**Optimization**: Group patterns with common prefixes to reduce redundant `contains()` calls.

**❌ Redundant Checks:**
```vrl
if contains(msg, "user") && contains(msg, "invalid") { .type = "invalid_user" }
else if contains(msg, "user") && contains(msg, "valid") { .type = "valid_user" }
else if contains(msg, "user") && contains(msg, "admin") { .type = "admin_user" }
```

**✅ Nested Structure (Fewer Operations):**
```vrl
if contains(msg, "user") {
    if contains(msg, "invalid") { .type = "invalid_user" }
    else if contains(msg, "valid") { .type = "valid_user" }
    else if contains(msg, "admin") { .type = "admin_user" }
}
```

**VPI Impact**: 3 `contains()` calls → 1-2 `contains()` calls (50%+ CPU reduction)

### 8.1 Selective, cheap guards first
```vrl
m = string!(.message)

if starts_with(m, "pam_unix(sshd:session): session opened") {
  .ssh_event = "open"
} else {
  if starts_with(m, "pam_unix(sshd:session): session closed") {
    .ssh_event = "close"
  } else {
    if contains(m, "Invalid user ") {
      .ssh_event = "invalid_user"
    }
  }
}
```

### 8.2 Combined branch with single split
```vrl
if contains(m, "Invalid user ") {
  rest = split(m, "Invalid user ")[1] ?? ""
  from_parts = split(rest, " from ")
  .ssh_user = from_parts[0] ?? null
  .ssh_ip   = from_parts[1] ?? null
}
```

### 8.3 Multi-field classification
```vrl
.code  = to_int(.status) ?? 0
.level = (.code >= 500 ? "error" : (.code >= 400 ? "warn" : "info"))
.type  = (contains(m, "timeout") ? "timeout" : "generic")
```

### 8.4 Early skips (no-op)
```vrl
# Do nothing if not nginx
if !contains(m, "nginx") { abort }   # requires drop_on_abort strategy
```

### 8.5 Whitelist routing booleans (for filter/route)
```vrl
# In a `filter` transform, you only return boolean
starts_with(string!(.source), "service/") && (.level == "error")
```

---

## 9) Iteration (map/for_each) & Object Walking
### 9.1 Map values (cleanup empty strings)
```vrl
. = map_values(., recursive: true) -> |v| { v == "" ? null : v }
```

### 9.2 Map keys (uppercasing)
```vrl
. = map_keys(., recursive: true) -> |k| { upcase(k) }
```

### 9.3 for_each array
```vrl
total = 0.0
for_each(.durations) -> |i, d| {
  total = total + (to_float(d) ?? 0.0)
}
.total_duration = total
```

### 9.4 Select subset
```vrl
clean = {}
for_each(["method","path","status"]) -> |i, k| {
  if exists(.{k}) { clean[k] = .{k} }
}
.selected = clean
```

### 9.5 Transform array of objects
```vrl
.items = map(.items) -> |it| {
  it.price = to_float(it.price) ?? 0.0
  it.qty   = to_int(it.qty) ?? 1
  it.total = it.price * it.qty
  it
}
```

---

## 10) Nulls, Existence & Defaults
### 10.1 exists / null checks
```vrl
if exists(.request_id) { .rid = .request_id }
```

### 10.2 Default with `??`
```vrl
.env = .env ?? "prod"
```

### 10.3 Nested get with default
```vrl
.region = get(.labels, ["aws", "region"]) ?? "unknown"
```

### 10.4 Safe bool default
```vrl
.ok = (to_bool(.ok) ?? false)
```

---

## 11) Types & Conversions
### 11.1 Numbers
```vrl
i = to_int(.i) ?? 0
f = to_float(.f) ?? 0.0
```

### 11.2 Strings
```vrl
# Prefer string!/to_string! once; reuse variable
s = string!(.i)
```

### 11.3 Booleans
```vrl
b = (.flag == "true") ? true : false
```

### 11.4 Arrays & objects
```vrl
is_arr = is_array(.x)
is_obj = is_object(.y)
```

### 11.5 Length vs strlen
```vrl
# length counts bytes for strings; use strlen for characters
bytes = length(.s)
chars = strlen(.s)
```

---

## 12) Merging, Renaming, Restructuring
### 12.1 Shallow merge
```vrl
. = merge(., { "service": "web", "env": "prod" })
```

### 12.2 Deep-ish via assign
```vrl
if !exists(.meta) { .meta = {} }
.meta.host = (.meta.host ?? .host)
```

### 12.3 Bulk rename pattern
```vrl
rename = { "msg":"message", "usr":"user", "ts":"timestamp" }
for_each(keys(rename)) -> |i, k| {
  new = rename[k]
  if exists(.{k}) { .{new} = del(.{k}) }
}
```

### 12.4 Split event into many
```vrl
lines = split(string!(.message), "\n")
. = map(lines) -> |ln| { { "line": ln } }    # N events emitted
```

---

## 13) Early Exits, Guard Clauses & Performance
**Goal:** Skip heavy work ASAP, do cheap checks first, split once, cache once.

### 13.1 Guard & skip
```vrl
m = string!(.message)
if !contains(m, "nginx") { abort }
```

### 13.2 Anchors before contains
```vrl
if starts_with(m, "GET ") {
  # parse path, etc.
} else {
  if starts_with(m, "POST ") {
    # parse differently
  } else {
    if contains(m, "HTTP/1.") { .http = true }
  }
}
```

### 13.3 Split once, reuse twice
```vrl
if contains(m, "Invalid user ") {
  rest = split(m, "Invalid user ")[1] ?? ""
  fp   = split(rest, " from ")
  .user = fp[0] ?? null
  .ip   = fp[1] ?? null
}
```

### 13.4 Cache conversions
```vrl
uid = to_int(.uid) ?? -1
if uid >= 1000 { .user_class = "regular" }
```

### 13.5 Avoid repeated downcase
```vrl
ml = downcase(m)
if contains(ml, "warn") { .level = "warn" }
```

---

## 14) Performance Guide — BAD / AVOID / GOOD + Cheap Ops
### BAD (never / only last resort)
- **Regex:** **NEVER use regex** (HyperSec policy). Use `parse_*` or split/anchors instead.
- Re-parsing JSON/timestamps repeatedly.
- Repeated `string!(.message)`/`downcase(m)` in same branch.

### AVOID (unless necessary)
- Many `contains` over the same large string.
- Multiple `split` on same delimiter — split once, reuse.
- Per-event enrichments with high latency.

### GOOD (prefer)
- `starts_with`/`ends_with` anchors.
- One split per delimiter; reuse parts.
- Built-in `parse_*` over ad-hoc parsing.
- Coalesce defaults; handle errors locally.

### Cheap ops & pointer-like casts (heuristics)
- **Assignment / field aliasing:** `.x = .y` — effectively copying a reference/value; cheap for small scalars.
- **Type assertions / force-typing:** `string!(x)`, `to_string!(x)` — cheap compared to parsing; prefer once per hot path and reuse.
- **Shallow merges:** `merge(., obj)` — efficient for small/medium objects; cheaper than reconstructing fields individually.
- **Length/startswith/endswith:** inexpensive compared to regex; anchor checks avoid full scans when token position is known.
- **`exists`, `get` with default:** cheap presence checks; avoid exceptions and extra parsing.
- **Null coalesce `??`:** control-flow shortcut; cheaper than branching when just providing defaults.

> Rule of thumb: **Parse once, cast once, split once, cache once.**

---

## 15) Multi-Transform Architecture Patterns (YAML)
### 15.1 Parse → Enrich → Normalise
```yaml
transforms:
  parse:
    type: remap
    source: |
      obj = parse_json(.message) ?? {}
      . = merge(., obj)

  enrich:
    type: remap
    inputs: [parse]
    source: |
      .service = (.service ?? "web")
      .region  = (.region  ?? "ap-southeast-2")

  normalize:
    type: remap
    inputs: [enrich]
    source: |
      .code  = to_int(.status) ?? 0
      .level = (.code >= 500 ? "error" : (.code >= 400 ? "warn" : "info"))
```

### 15.2 Route by VRL boolean
```yaml
transforms:
  only_errors:
    type: filter
    inputs: [parse]
    condition:
      type: vrl
      source: "to_int(.status) ?? 0 >= 500"
```

### 15.3 Dead-letter (drop on abort/error)
```yaml
transforms:
  parse:
    type: remap
    drop_on_error: true
    drop_on_abort: true
    reroute_dropped: true
    source: |
      . = parse_json!(.message)
```

---

## 16) Metrics Caveats
- Metrics have a strict schema; some fields are read-only.
- Use VRL minimally on metrics (e.g., add tags). For heavy logic, use metric transforms.

**Example:**
```vrl
# Safe: add tag
if !exists(.metric.tags) { .metric.tags = {} }
.metric.tags.service = (.metric.tags.service ?? "web")
```

---

## 17) Testing VRL (YAML tests)
```yaml
tests:
  - name: "status parsing"
    inputs:
      - insert_at: normalize
        type: log
        log_fields:
          message: "status=404"
    outputs:
      - extract_from: normalize
        conditions:
          - type: vrl
            source: |
              assert_eq!(.code, 404)
              assert_eq!(.level, "warn")
```

---

## 18) Advice for Python & Java Developers
- **Error handling is explicit** (like Go/Rust): use `!`, `??`, or `val, err =`.
- **No UDFs**: refactor into multiple transforms or include files.
- **Iteration is functional**: `map`, `for_each`, no `for/while`.
- **No libraries/HTTP**: VRL is sandboxed; rely on built-ins.
- **Think record-by-record**: one event in, one out (or N via array).

**Gotcha rewrites:**

**Pythonic truthiness (INVALID)**
```vrl
# WRONG: .message isn't a boolean
if .message { .ok = true }
```
**VRL way**
```vrl
if exists(.message) && strlen(string!(.message)) > 0 { .ok = true }
```

**Java try/catch (NONEXISTENT) → VRL**
```vrl
# WRONG: no try/catch
# RIGHT:
val, err = to_int(.count)
if err != null { .count = 0 } else { .count = val }
```

**Loop index style (UNAVAILABLE) → VRL**
```vrl
# RIGHT:
sum = 0
for_each(.nums) -> |i, n| { sum = sum + (to_int(n) ?? 0) }
.total = sum
```

---

## 19) HyperSec DFE Integration Guide

### 19.1) DFE Pipeline Architecture
**HyperSec Data Fusion Engine (DFE)** processes logs through multiple stages:

1. **Edge Stream Hub (ESH)**: Extracts standard syslog headers (`timestamp`, `hostname`, `facility`, etc.)
2. **101-transform**: Flattens JSON messages (`parse_json(.message) ?? {}`)
3. **Your VRL**: Extracts semantic fields from message content
4. **DFE Schema**: Maps to standardized field types and names

### 19.2) Field Conflict Prevention
**CRITICAL**: DFE reserves specific field names that VRL **CANNOT** use:

**Reserved Fields (24 total):**
- `timestamp`, `timestamp_*` (all timestamp variants)
- `event_hash`, `logoriginal`, `logjson`, `org_id`
- `tags.*` (entire tags namespace)

**✅ Use Safe Alternatives:**
```vrl
# ❌ WRONG: Reserved field names
.timestamp = parse_timestamp!(ts)
.hostname = "server1"
.event_hash = "abc123"

# ✅ CORRECT: Alternative field names  
.log_timestamp = parse_timestamp!(ts)
.source_hostname = "server1"
.ssh_event_id = "abc123"
```

**Naming Convention**: Prefix fields with source type (`ssh_*`, `apache_*`, `cisco_*`)

### 19.3) Meta Schema Type Assignment
**DFE uses 23 meta schema types** for field optimization:

**High-Performance Types:**
- `string_fast`: Heavily queried fields (usernames, IPs, event types)
- `string_fast_lowcardinality`: Queried + limited values (log levels, status)
- `ipv4`/`ipv6`: IP addresses (specialized indexing)
- `int32`: Port numbers, counts
- `text`: Large message content

**Selection Logic:**
```vrl
# Examples of proper type assignment:
.ssh_username = user_str        # → string_fast (heavily queried)
.ssh_event_type = "invalid"     # → string_fast_lowcardinality  
.ssh_source_ip = "192.168.1.1"  # → ipv4 (specialized type)
.ssh_source_port = 22           # → int32 (port number)
.ssh_message_detail = msg       # → text (large content)
```

### 19.4) Message Processing Patterns

**✅ After ESH + 101-Transform:**
```vrl
# Standard DFE pattern - fields may already be parsed
message_str = to_string(.message ?? .msg ?? .discovery) ?? ""

# Check if syslog fields already extracted by ESH
if !exists(.hostname) && !exists(.timestamp) {
    # ESH didn't run - parse syslog ourselves
    parsed = parse_syslog!(message_str)
    .source_hostname = parsed.hostname  # Use source_ prefix
    .log_timestamp = parsed.timestamp   # Avoid reserved timestamp
    message_content = parsed.message
} else {
    # ESH already extracted headers - work with content
    message_content = message_str
}

# Extract semantic fields from message content
if contains(message_content, "error") {
    .ssh_event_type = "error"  # Semantic extraction
}
```

### 19.5) DFE Performance Optimization
**VPI (VRL Performance Index)** targets for DFE deployment:

- **Excellent**: 5000+ VPI (400+ events/CPU%)
- **Good**: 2000+ VPI (200+ events/CPU%)  
- **Acceptable**: 500+ VPI (50+ events/CPU%)

**DFE-Optimized Patterns:**
```vrl
# Early exits for irrelevant logs
if !contains(message_str, "sshd") && !contains(message_str, "ssh") {
    abort  # Drop non-SSH logs immediately
}

# Nested conditions for common patterns
if contains(message_str, "authentication") {
    if contains(message_str, "failure") { .ssh_event_type = "auth_fail" }
    else if contains(message_str, "success") { .ssh_event_type = "auth_success" }
}
```

### 19.6) DFE Multi-Domain Support
**DFE serves multiple domains beyond cybersecurity:**

**Domain-Aware Field Naming:**
```vrl
# Cybersecurity domain
.ssh_threat_level = "high"
.ssh_attack_vector = "brute_force"

# Network operations domain  
.ssh_connection_quality = "degraded"
.ssh_bandwidth_usage = "normal"

# Compliance domain
.ssh_audit_event = "user_access"
.ssh_compliance_status = "compliant"
```

**Generic Approach**: Use `parsed_*` prefix when domain is unclear.

---

## 20) Appendix: Mini Cheatsheet
**Common built-ins (illustrative):**
```vrl
# Types / checks
is_string(.x) is_integer(.x) is_array(.x) is_object(.x)

# Strings
length(.s) strlen(.s) upcase(.s) downcase(.s) trim(.s)
starts_with(.s, "a") ends_with(.s, "z") contains(.s, "mid")
split(.s, " ") replace(.s, "a", "b")

# Parsing
parse_json(.m) parse_timestamp(.t, "%+") parse_duration(.d, "s")

# Numbers
to_int(.x) to_float(.x)

# Objects
merge(., other) get(., ["a","b"]) del(.field)

# Iteration
map(.arr) -> |v| { ... }
for_each(.arr) -> |i, v| { ... }
map_keys(., recursive: true) -> |k| { ... }
map_values(., recursive: true) -> |v| { ... }

# Debug / test
log("msg", level: "debug") assert!(cond) assert_eq!(a, b)
abort
```

---

## 21) LLM Generation Checklist & Anti-Hallucination Notes
**Checklist (use for prompts):**
- Target **Vector.dev VRL** (no UDFs, no external I/O).
- **ALWAYS start with type safety**: `field_str = if exists(.field) { to_string(.field) ?? "" } else { "" }`
- Cache string conversions **once** and reuse.
- Prefer `starts_with`/`ends_with` over `contains` when anchored.
- For each delimiter, **split once** and reuse.
- Handle fallible ops: `!`, `??`, or `val, err =`.
- Use `merge` to enrich instead of replacing root blindly.
- **Nest common conditions** to reduce redundant checks.
- Use `abort` (not `return`) with deliberate drop strategy.
- Provide short comments **above** blocks.
- Output only event mutations; avoid invented APIs/keywords.

### 20.1) LLM Anti-Patterns (What AI Gets Wrong)
**Critical patterns to avoid in AI-generated VRL:**

• **Bare return statements**: 
  ```vrl
  return  # ❌ E203 syntax error
  ```
  Use `abort` instead.

• **Function calls in array indices**: 
  ```vrl
  parts[length(parts) - 1]  # ❌ E203 syntax error
  ```
  **✅ Correct approach**: Use variables for dynamic indexing:
  ```vrl
  last_idx = length(parts) - 1
  if last_idx >= 0 { .last_part = parts[last_idx] }
  ```

• **Unnecessary coalescing on infallible operations**:
  ```vrl
  parts = split(text, " ") ?? []  # ❌ E651 error
  ```
  Remove `?? []` from `split()` on string literals.

• **Direct field operations without type safety**:
  ```vrl
  if contains(.message, "error") { ... }  # ❌ E110 error
  ```
  Always use type-safe variables first.

• **Complex nested splits**:
  ```vrl
  user = split(split(.message, " for ")[1], " from ")[0]  # ❌ Hard to debug
  ```
  Split once, store intermediate results, then split again.

### 20.2) AI Success Patterns
**Patterns that work well for AI-generated VRL:**

• **Type safety first**: Always start with field type conversion
• **Simple conditionals**: Use clear if-else chains  
• **Descriptive variables**: `user_part`, `ip_section`, `port_str`
• **Bounds checking**: Always check `length(parts) >= N` before indexing
• **Single responsibility**: One parsing task per code block

**Anti-hallucination facts:**
- No user-defined functions or imports.
- No general loops; only iteration helpers.
- No network/file I/O.
- Errors must be handled or compile will fail.
- `.` is the current event; setting `.` to an array emits multiple events.
- After 101-transform, `.message` contains log content only (not full syslog).
