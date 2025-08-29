# VRL CPU Cost Guide (Vector 0.49)
**Goal:** Maximise CPU efficiency and throughput for VRL across `remap`, `filter`, `route`, and `reduce` transforms.  
**Context:** Input arrives as JSON from Kafka. Enrichment tables are used (prefer memory tables). No Lua/WASM/tokenizer. Timestamp parsing is relevant but secondary.

---

## QUICK RULES (Prompt‑style)
- **NEVER use regex in VRL.** Replace with format‑specific parsers or simple string ops.
- **AVOID heavy parsing or conversions in hot paths.** Parse once, reuse many times.
- **PREFER keyed lookups, direct field access, and simple predicates.** Keep expressions shallow.

You can paste the sections below into LLM prompts (OpenAI/Anthropic/Gemini) or internal docs.

---

## BAD — never do
- **Regex of any kind** (e.g., using `parse_regex`, `match` with regex patterns, or any regex‑enabled variant):  
  - **Why:** Compiles/evaluates patterns per event; very high CPU; kills throughput.  
  - **Instead:** Use format‑specific parsers (`parse_json!`, `parse_csv!`, `parse_syslog!`, etc.) or simple substring checks (`contains`, `starts_with`, `ends_with`).  
  - **Example (avoid):**  
    ```vrl
    # SLOW: regex capture
    .user = parse_regex!(.message, r'(?P<user>\w+)').user
    ```

- **Wide/scan‑like enrichment fetches** (unbounded multi‑row queries):  
  - **Why:** Iterates many rows; CPU grows with table size/result set.  
  - **Instead:** Design tables with **unique, selective keys** and use single‑row lookups.  
  - **Example (avoid):**  
    ```vrl
    # SLOW: broad multi-row fetch (pattern/example name only)
    rows = get_enrichment_table_records("ip_info", {"asn": .asn})
    ```

- **Redundant repeated parsing** of the same field per event:  
  - **Why:** Each parse call costs CPU; repeating it compounds the cost.  
  - **Instead:** Parse once, store the result, reuse.  
  - **Example (avoid):** calling `parse_json!` multiple times on `.message` in the same program.

---

## AVOID — only when there is no alternative
- **Timestamp parsing (`parse_timestamp!`) on arbitrary formats:**  
  - **Why:** Date/time format parsing is relatively expensive.  
  - **Do this instead:** Prefer native epoch numbers or standard formats already parsed upstream; if needed, parse once and cache in `.ts`.  
  - **Example:**  
    ```vrl
    .ts = parse_timestamp!(.time, format: "%Y-%m-%dT%H:%M:%S%.fZ")
    ```

- **Repeated type conversions** (`to_string!`, `to_int!`, `to_float!`, etc.) in hot paths:  
  - **Why:** Allocations + conversions add up at scale.  
  - **Do this instead:** Keep data in native type until you must output/compare; convert once if needed.

- **Content decoding/encoding** (e.g., Base64) on every event:  
  - **Why:** Transforming large payloads per event is CPU heavy.  
  - **Do this instead:** Perform decoding upstream where possible or gate it with a strict condition so it runs on a tiny subset.

- **Complex URL/header/body parsing** for simple checks:  
  - **Why:** Full parsers do more work than needed.  
  - **Do this instead:** Use substring checks for lightweight routing (e.g., `contains(.path, "/health")`).

- **Multi‑row enrichment queries** (`get_enrichment_table_records`) as routine path:  
  - **Why:** Returns multiple rows → more CPU per event + merging logic.  
  - **Do this instead:** Use **single‑row** keyed lookups (`get_enrichment_table_record`) with selective keys; pre‑shape the table to match lookups.

---

## GOOD — prefer these
- **Direct field access and simple predicates:**  
  - **Why:** Reads/comparisons/arithmetic are cheap.  
  - **Pattern:** Keep conditions flat and explicit.  
  - **Example:**  
    ```vrl
    .sev = to_int!(.severity) ?? 0
    if .sev >= 5 || .level == "error" { .alert = true }
    ```

- **Format‑specific parsers** rather than regex:  
  - **Why:** Implemented in Rust with optimised paths.  
  - **Examples:** `parse_json!`, `parse_csv!`, `parse_syslog!`, `parse_common_log!`  
  - **Tip:** If your Kafka source can decode JSON, prefer decoding at source so VRL receives structured fields.

- **Simple string ops** (non‑regex):  
  - **Why:** Linear time, allocation‑light.  
  - **Examples:** `contains(.message, "health")`, `starts_with`, `ends_with`, `split` by static delimiter.

- **Keyed memory‑table lookups** (`get_enrichment_table_record`):  
  - **Why:** Hash/index lookups are fast; constant‑time-ish.  
  - **Pattern:** Build tables keyed by a unique/selective field (e.g., `user_id`, `ip_cidr_exact`).  
  - **Example:**  
    ```vrl
    row, err = get_enrichment_table_record("users", {"user_id": string!(.uid)})
    if err == null && is_object(row.value) { . |= row.value }
    ```

- **Parse once, reuse many times:**  
  - **Why:** Amortises cost across downstream logic.  
  - **Example:**  
    ```vrl
    # Good: parse once
    .obj, err = parse_json(.message)
    if err == null { . |= .obj }
    ```

- **Short‑circuiting & coalescing**:  
  - **Why:** Avoids unnecessary work and errors.  
  - **Examples:**  
    ```vrl
    # Try a fast path first; fall back only if needed
    .svc = .service ?? .app ?? "unknown"

    # Guard heavy ops
    if exists(.maybe_base64) && length!(.maybe_base64) < 4096 {
      .decoded, err = decode_base64(.maybe_base64)
    }
    ```

- **Use `abort` early for drops** (with `drop_on_abort = true`):  
  - **Why:** Short‑circuits processing for junk events.  
  - **Example:**  
    ```vrl
    if .level == "debug" { abort "drop noisy debug" }
    ```

---

## Reference Patterns (copy/paste)
**Fast routing/filtering**
```vrl
if .status >= 500 || (.level ?? "info") == "error" { .is_error = true }
```

**Keyed enrichment (fast)**
```vrl
user_id = string!(.uid)
row, err = get_enrichment_table_record("users", {"user_id": user_id})
if err == null && is_object(row.value) { .user |= row.value }
```

**Parse once, reuse**
```vrl
obj, err = parse_json(.message)
if err == null { . |= obj }
```

**Guard expensive work**
```vrl
if exists(.payload_b64) && length!(.payload_b64) <= 4096 {
  .payload_raw, err = decode_base64(.payload_b64)
}
```

---

## Checklist (use in reviews & prompts)
- [ ] No regex anywhere in VRL.
- [ ] Only **keyed** enrichment lookups in the hot path; no multi‑row scans.
- [ ] Parse JSON **once**; avoid re‑parsing or large payload transforms.
- [ ] Timestamp parsing used sparingly; prefer epoch or pre‑parsed formats.
- [ ] Keep expressions shallow; no repeated conversions; coalesce/short‑circuit.
- [ ] Early `abort` for drops; strip debug/noisy events upstream when possible.

---

## Notes
- These guidelines target Vector **0.49** and emphasise CPU over everything else.
- When in doubt, measure with representative data and `vector vrl --input sample.json --program prog.vrl`.
