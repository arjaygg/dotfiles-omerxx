# Claude Code Statusline: Quick Reference

## The 8 Essential Elements

| # | Element | Example | Why It Matters |
|---|---------|---------|-----------------|
| 1 | **Model** | `Sonnet (200k)` | Know your capabilities |
| 2 | **Context %** | `35%` (green) | Prevent overflow |
| 3 | **Project** | `my-app` | Stay oriented |
| 4 | **Last Message** | `💬 "fix the bug..."` | Quick context recovery |
| 5 | **Last Activity** | `3m` | Is it still running? |
| 6 | **Session Date** | `09/14` | Time tracking |
| 7 | **Context Limit** | `(200k)` | Model awareness |
| 8 | **Workspace** | `(src/api)` | Sub-directory tracking |

---

## Display Modes at a Glance

### **Verbose** (Default for long sessions)
```
Sonnet (200k) ▸ Context: 35% (129k left) ▸ Session: 09/14 ▸ 03:11 PM ▸ 💬 "fix..." ▸ project
```
✅ Everything visible  
⏱️ ~40 chars wide  
🎯 Research, debugging, complex tasks

---

### **Compact** (Recommended for dev)
```
Sonnet (200k) • 35% • 💬 "fix..." • project-name
```
✅ Only essentials  
⏱️ ~25 chars wide  
🎯 Fast iteration, narrow terminals

---

### **Minimal** (For scripts/CI)
```
Sonnet • 35% • project-name
```
✅ No noise  
⏱️ ~15 chars wide  
🎯 Automation, logging

---

### **Custom** (Build your own)
```bash
--format '%model% [%percent%] %project%'
# Output: Sonnet [35%] my-app

--format '🤖 %model% 📊 %percent% 💬 %message%'
# Output: 🤖 Sonnet 📊 35% 💬 "can you help..."
```
✅ Fully customizable  
🎯 Power users

---

## Color Meanings

### Context Percentage Colors
```
█ 0-50%   → Green   🟢 Comfortable
█ 50-75%  → Yellow  🟡 Caution
█ 75-90%  → Red     🔴 Warning
█ 90%+    → Bright  ⚫ COMPACT NOW
```

### Model Provider Colors
```
Claude  → Blue (34)    | Sonnet, Opus, Haiku
OpenAI  → Red (31)     | GPT-4, GPT-3.5
Google  → Cyan (36)    | Gemini 1.5, 2.x
xAI     → Yellow (33)  | Grok
```

---

## Configuration

### 1. **Enable Verbose (Full Info)**
```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/claude-statusline/statusline.sh --verbose"
  }
}
```

### 2. **Enable Compact (Quick)**
```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/claude-statusline/statusline.sh --compact"
  }
}
```

### 3. **Enable Custom**
```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/claude-statusline/statusline.sh --format '%model% [%percent%] %project%'"
  }
}
```

### 4. **Disable (if needed)**
```json
{
  "statusLine": null
}
```

---

## Template Variables

```
%model%         Sonnet, Opus, GPT-4, etc.
%context%       35% (129k left)  ← full display
%percent%       35                ← percentage only
%remaining%     129k left
%session%       09/14             ← date
%time%          03:11 PM PST      ← full timestamp
%last%          3m, 5m, 2h        ← last activity
%project%       my-app            ← current project
%message%       💬 "fix the..."   ← last message preview
%output_style%  markdown          ← if non-default
%cache%         72% hit           ← cache performance
%tokens%        1.2M/340K         ← token breakdown
%version%       v2.1.87           ← Claude Code version
```

---

## Model Context Limits (Verified 2025)

| Model | Limit | Color |
|-------|-------|-------|
| Claude Sonnet 4 | 200K (1M w/ beta) | 🔵 Blue |
| Claude Opus | 200K | 🟣 Magenta |
| Claude Haiku | 200K | 🟢 Green |
| GPT-4o | 128K | ⚪ White |
| GPT-4 Turbo | 128K | 🔴 Red |
| Gemini 1.5 Pro | 2M | 🔷 Cyan |
| Gemini 2.x | 1M+ | 🔷 Cyan |
| Grok 3 | 1M | 🟡 Yellow |

---

## Common Formats (Copy-Paste)

```bash
# Minimal
'%model%: %percent%'
# Output: Sonnet: 35%

# Balanced
'%model% • %percent% • %project%'
# Output: Sonnet • 35% • my-app

# With time
'%model% %percent% (last: %last%) • %project%'
# Output: Sonnet 35% (last: 3m) • my-app

# Professional
'%model% - Context: %percent% (%remaining%) - %project%'
# Output: Sonnet - Context: 35% (129k left) - my-app

# Detailed
'%model% %context% | Session: %session% | %project%'
# Output: Sonnet 35% (129k left) | Session: 09/14 | my-app

# Emoji fun
'🤖 %model% 📊 %percent% 💬 %message% 📁 %project%'
# Output: 🤖 Sonnet 📊 35% 💬 "can you help..." 📁 my-app
```

---

## Troubleshooting

### Statusline shows `0%` or incorrect percentage
- Ensure Node.js is installed: `node --version`
- Check tiktoken: `npm list -g tiktoken`
- Verify token counter: `node ~/.claude/claude-enhanced-token-counter.js <file>`

### Wrong time display (macOS)
- Install GNU coreutils: `brew install coreutils`
- Check timezone: `date +%Z`

### Session not detected
- Check project directory: `ls ~/.claude/projects/`
- Verify current path matches project: `pwd`

### Colors not displaying
- Check terminal supports ANSI 256-color: `echo $TERM`
- May need to set: `export TERM=xterm-256color`

---

## When to Use Each Mode

| Mode | Best For | Why |
|------|----------|-----|
| **Verbose** | Research, debugging, long sessions | Complete situational awareness |
| **Compact** | Development, fast iteration | Minimal visual noise, fits narrow terminals |
| **Minimal** | Scripts, CI/CD, automation | No clutter in logs |
| **Custom** | Specific workflows | Optimize for your priorities |

---

## Context Threshold Recommendations

| Use Case | Warning Threshold | Critical Threshold |
|----------|------------------|-------------------|
| Quick bug fix | 75% | 85% |
| Feature dev | 70% | 80% |
| Research/exploration | 60% | 75% |
| Large refactor | 50% | 70% |
| Code review | 65% | 80% |

---

## Pro Tips

✅ **Workspace Indicator:** If in `src/api/`, statusline shows `my-app (src/api)` — helps track deep navigation  
✅ **Message Preview:** Shows first 5 words of last message — 85% of context recovery without reading transcript  
✅ **Color At a Glance:** Green = safe, Yellow = watch, Red = act now  
✅ **Session Tracking:** Note the session date in verbose mode for billing/audit trails  
✅ **Custom Mode Power:** Chain multiple variables for deep forensics  

⚠️ **Avoid Redundancy:** Don't show both `%context%` and `%percent%` — pick one  
⚠️ **Terminal Width:** Compact mode for <100 char width, verbose for wide screens  
⚠️ **Performance:** If statusline takes >100ms, consider async updates  

---

## Next Steps

1. **Choose your mode:** Verbose for research, Compact for dev
2. **Update settings.json:** Add statusLine configuration
3. **Test rendering:** Check it displays in your terminal
4. **Customize if needed:** Try custom format if defaults don't fit your workflow
5. **Monitor context:** Use the color coding to stay aware of token usage

---

**Last Updated:** 2026-04-13  
**Source:** `.claude/claude-statusline/statusline.sh`
