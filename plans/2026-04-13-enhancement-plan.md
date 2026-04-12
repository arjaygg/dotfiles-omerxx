# Enhancement Plan: Statusline.sh Improvements

**Date:** 2026-04-13  
**Branch:** updatestatusline  
**Goal:** Enhance `statusline.sh` based on comprehensive research findings

---

## Current State Assessment

### ✅ Already Implemented
- [x] Context percentage calculation with color coding (green/yellow/red)
- [x] Model detection & provider-specific color coding
- [x] Multiple display modes (verbose, compact, custom)
- [x] Template variables (%model%, %percent%, %project%, etc.)
- [x] Workspace/subdirectory indicator
- [x] Last message preview (first 5 words)
- [x] Cache metrics extraction (cache_read_input_tokens, cache_creation_input_tokens)
- [x] Platform-specific timestamp parsing (macOS, Linux, Windows)
- [x] Session auto-detection (scanning ~/.claude/projects/)
- [x] Model context limit detection (Claude, GPT, Gemini, Grok)

### ⚠️ Needs Enhancement
- [ ] **Cache hit rate calculation** — currently extracted but not formatted/displayed
- [ ] **Token breakdown display** — input/output split not shown in any mode
- [ ] **Session continuity indicator** — no indication if resumed from checkpoint
- [ ] **Context trend indicator** — no visual feedback on context rising/stable/falling
- [ ] **Intelligent thresholds** — warnings are fixed (75%+), should vary by task type
- [ ] **Compression recommendations** — no proactive suggestion when to compact
- [ ] **Theme detection** — basic theme field exists but not used for color adjustment
- [ ] **Performance metrics** — response time tracking/optimization

### ❌ Missing Features (From Research)
1. **Cache hit percentage** — `% = cache_read / (cache_read + usage_input) * 100`
2. **Token economics** — show token ratio: `input:output` or `1.2M/340K`
3. **Time-to-compact warning** — estimate remaining messages before context overflow
4. **Session duration** — track how long session has been open
5. **Workspace depth indicator** — show nesting level in project subdirectories
6. **Model cost awareness** — optional flag to warn about expensive models at high context
7. **Compaction history** — track how many times session has been compacted
8. **Beta feature detection** — identify when using beta headers (Sonnet 1M mode)

---

## Enhancement Roadmap

### Phase 1: Cache & Token Metrics (Core)
**Priority:** HIGH | **Impact:** Medium | **Effort:** Low

**What:** Add cache hit rate calculation and token display templates

**Changes:**
```bash
# File: statusline.sh (new function)
calculate_cache_hit_rate() {
    local cache_read="${1:-0}"
    local usage_input="${2:-0}"
    local total=$((cache_read + usage_input))
    
    if [[ $total -eq 0 ]]; then
        echo "0"
        return
    fi
    
    echo "$((cache_read * 100 / total))"
}

# Usage in template:
cache_hit_percent=$(calculate_cache_hit_rate "$cache_read_tokens" "$usage_input_tokens")
cache_info="$(printf "%d%% cache" "$cache_hit_percent")"
```

**New Template Variables:**
- `%cache_hit%` — `72%` (percentage only)
- `%cache%` — `72% cache` (human readable)
- `%tokens_input%` — `1.2M` (input tokens)
- `%tokens_output%` — `340K` (output tokens)
- `%tokens_ratio%` — `1.2M/340K` (input:output ratio)

**Display Examples:**
```
Compact: Sonnet • 35% • 72% cache • project
Custom:  %model% [%percent%] (%cache_hit%) • %tokens_ratio%
Output:  Sonnet [35%] (72%) • 1.2M/340K
```

---

### Phase 2: Context Trend & Warnings (Safety)
**Priority:** HIGH | **Impact:** High | **Effort:** Medium

**What:** Add context trend indicator and smart thresholds

**Changes:**
```bash
# File: statusline.sh (new function)
calculate_context_trend() {
    local current="$1"
    local previous="${2:-0}"
    
    if [[ $current -gt $((previous + 5)) ]]; then
        echo "↑"  # Context climbing
    elif [[ $current -lt $((previous - 5)) ]]; then
        echo "↓"  # Context falling (compaction likely)
    else
        echo "→"  # Stable
    fi
}

get_warning_threshold() {
    local task_type="${1:-generic}"
    
    case "$task_type" in
        "quick_fix")     echo "80" ;;
        "feature_dev")   echo "70" ;;
        "research")      echo "60" ;;
        "refactor")      echo "50" ;;
        "code_review")   echo "65" ;;
        *)               echo "75" ;;
    esac
}
```

**New Template Variables:**
- `%trend%` — `↑` or `→` or `↓`
- `%warning%` — `⚠️` (shown only when needed)
- `%critical%` — `🚨` (shown only when >90%)

**Display Examples:**
```
Verbose:  Sonnet (200k) ▸ Context: 35% → ▸ (safe) ▸ project
Critical: Sonnet (200k) ▸ Context: 92% ↑ 🚨 ▸ COMPACT NOW ▸ project
```

---

### Phase 3: Session Continuity (Context Awareness)
**Priority:** MEDIUM | **Impact:** Medium | **Effort:** High

**What:** Detect resumed sessions and show continuity indicators

**Changes:**
```bash
# File: statusline.sh (new function)
detect_session_checkpoint() {
    local transcript_path="$1"
    
    # Look for .checkpoint files associated with this session
    local checkpoint_dir="${transcript_path%/*}/.checkpoints"
    if [[ -d "$checkpoint_dir" ]]; then
        local checkpoint_count=$(ls -1 "$checkpoint_dir" 2>/dev/null | wc -l)
        if [[ $checkpoint_count -gt 0 ]]; then
            local latest_checkpoint=$(ls -t "$checkpoint_dir" | head -1)
            local checkpoint_time=$(stat -f "%m" "$checkpoint_dir/$latest_checkpoint" 2>/dev/null || echo "0")
            local now=$(date +%s)
            local time_since=$((now - checkpoint_time))
            
            if [[ $time_since -lt 86400 ]]; then  # Within 24 hours
                echo "↻ resumed $(format_time_delta $time_since) ago"
            fi
        fi
    fi
}
```

**New Template Variables:**
- `%checkpoint%` — `↻ resumed 2h ago` (if applicable)

**Display Examples:**
```
Resumed:  Sonnet (200k) • 35% • [↻ resumed 2h ago] • project
```

---

### Phase 4: Intelligence & Recommendations (Advanced)
**Priority:** MEDIUM | **Impact:** Low (nice-to-have) | **Effort:** High

**What:** Proactive recommendations based on context trajectory

**Changes:**
```bash
# File: statusline.sh (new function)
estimate_compaction_need() {
    local current_percent="$1"
    local time_since_last_compact="${2:-999999}"
    local avg_tokens_per_minute="${3:-100}"
    
    if [[ $current_percent -ge 75 ]]; then
        local messages_remaining=$((((100 - current_percent) * context_limit) / avg_tokens_per_minute / 100))
        echo "⏺ Compact soon (~${messages_remaining} messages left)"
        return 0
    fi
    
    return 1
}
```

**New Template Variables:**
- `%recommendation%` — `⏺ Compact soon` (if needed)

**Display Examples:**
```
Warning:  Sonnet (200k) • 76% • ⏺ Suggest: /compact • project
```

---

## Implementation Priority

### Tier 1 (Do First)
1. ✅ Phase 1 — Cache hit rate + token metrics
   - **Why:** Core safety metric, low effort, high value
   - **Files:** statusline.sh (functions section, display templates)
   - **Time:** ~1-2 hours

2. ✅ Phase 2 — Context trend + smart warnings
   - **Why:** Prevents overflow, essential safety feature
   - **Files:** statusline.sh (warning logic, display modes)
   - **Time:** ~2-3 hours

### Tier 2 (Follow-up)
3. ⚠️ Phase 3 — Session continuity
   - **Why:** Nice-to-have, moderate complexity
   - **Files:** statusline.sh + checkpoint detection
   - **Time:** ~3-4 hours

### Tier 3 (Polish)
4. ❓ Phase 4 — Recommendations
   - **Why:** Advanced feature, lower priority
   - **Files:** statusline.sh (estimation logic)
   - **Time:** ~2-3 hours

---

## Testing Strategy

### Unit Tests
- [ ] Cache hit rate calculation (edge cases: 0, 100, partial)
- [ ] Context trend detection (↑ ↓ → transitions)
- [ ] Warning threshold logic (various task types)
- [ ] Template variable substitution

### Integration Tests
- [ ] All display modes with new variables
- [ ] macOS/Linux/Windows platform variations
- [ ] JSON input parsing (with/without cache fields)
- [ ] Fallback when JSON missing

### Manual Testing
- [ ] Verbose mode (full info)
- [ ] Compact mode (essential only)
- [ ] Custom formats (edge cases)
- [ ] Terminal width variations (80/120/180 chars)
- [ ] Color rendering on light/dark themes

---

## Files to Modify

| File | Scope | Lines | Priority |
|------|-------|-------|----------|
| `.claude/claude-statusline/statusline.sh` | Main implementation | ~1100 | PRIMARY |
| `.claude/claude-statusline/README.md` | Documentation | Add new variables | SECONDARY |
| `plans/statusline-quick-reference.md` | Reference guide | Already created | DONE |
| `plans/2026-04-13-statusline-research.md` | Research | Already created | DONE |

---

## Success Criteria

✅ **Phase 1 Complete:**
- Cache hit % displays correctly in verbose/compact modes
- Token breakdown template variables work
- No performance regression (<50ms render time)

✅ **Phase 2 Complete:**
- Context trend indicator shows (↑ ↓ →)
- Warning threshold respects task type
- Critical state (90%+) shows alert emoji

✅ **Overall:**
- All new features documented in README
- Quick reference updated with examples
- No breaking changes to existing modes
- Backward compatible (old configs still work)

---

## Next Steps

1. **Read & approve this plan** (you're reading it now!)
2. **Implement Phase 1** — cache metrics
3. **Test Phase 1** — verify display in all modes
4. **Implement Phase 2** — context trend warnings
5. **Test end-to-end** — all modes, all platforms
6. **Commit & document** — update README, quick ref
7. **Optional:** Implement Phase 3-4 if time permits

Ready to proceed? Start with Phase 1 implementation.

---

**Estimated Total Time:** 8-12 hours (including testing)  
**Risk Level:** Low (isolated feature additions, no breaking changes)  
**Review Needed:** Code review for platform compatibility (macOS/Linux/Windows)
