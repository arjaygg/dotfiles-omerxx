# Cursor IDE Setup Guide for 40+ Developer on MacBook Pro 2024

## ✅ Configuration Applied

Your Cursor has been optimized with:

### **Display & Readability**
- **Font Size**: 17px (comfortable for extended coding)
- **Line Height**: 1.6 (relaxed spacing for readability)
- **Letter Spacing**: 0.5px (reduces eye strain)
- **Theme**: Catppuccin Mocha (excellent for eyes - recommended over standard Dracula)
- **Font**: JetBrains Mono with ligatures enabled

### **Editor Features**
- ✅ Sticky scroll (keeps function signatures visible)
- ✅ Bracket pair colorization (easier code navigation)
- ✅ Smart indentation guides
- ✅ Inline hints (type information)
- ✅ Format on save (auto-cleanup)
- ✅ Minimap disabled (cleaner interface)

### **Performance**
- ✅ Optimized for M4 MacBook Pro (watcher exclusions)
- ✅ Large file optimizations enabled
- ✅ Smart caching configured

### **Keybindings Added**
- `cmd+i` → Cursor Agent Mode (AI pair programming)
- `cmd+k cmd+c` → Composer Mode
- `cmd+/` → Quick comment/uncomment
- `cmd+shift+f` → Format document
- `cmd+d` → Multi-select next occurrence
- `cmd+g` → Go to line
- `cmd+shift+o` → Go to symbol
- `f2` → Rename symbol
- `cmd+shift+r` → Refactor

---

## 🎯 Recommended Extensions

Install these for maximum productivity:

### **Essentials**
1. **Prettier** (esbenp.prettier-vscode) - Code formatter
   - Already configured in settings
2. **Python** (ms-python.python) - Python development
3. **Rust-analyzer** (rust-lang.rust-analyzer) - Rust support

### **Quality of Life**
4. **Thunder Client** (rangav.vscode-thunder-client) - API testing
5. **GitLens** (eamodio.gitlens) - Enhanced git integration
6. **Todo Tree** (Gruntfuggly.todo-tree) - Task tracking in code
7. **Error Lens** (usernamehw.errorlens) - Inline error/warning display
8. **Peacock** (johnpapa.vscode-peacock) - Color workspace tabs for multiple projects
9. **Better Comments** (aaron-bond.better-comments) - Highlight important comments

### **Optional (Language-Specific)**
- **Tailwind CSS IntelliSense** - For web development
- **MongoDB for VS Code** - Database exploration
- **REST Client** - Test APIs inline

---

## 🚀 Quick Start Checklist

- [ ] Restart Cursor IDE (⌘Q then reopen)
- [ ] Verify font rendering looks good
- [ ] Test keybindings:
  - Try `cmd+i` to open Agent mode
  - Try `cmd+d` to multi-select
  - Try `cmd+/` to comment lines
- [ ] Install recommended extensions via Extensions panel
- [ ] Check Theme (⌘K ⌘T) - should show "Catppuccin Mocha"
- [ ] Open a file and verify line height feels readable
- [ ] Test git features (cmd+shift+c for commit suggestion)

---

## 💡 Tips for Extended Coding Sessions

1. **Use Sticky Scroll** - Keep function signatures visible while scrolling
2. **Enable Breadcrumbs** - Navigate deep nested structures easily (⌘ Shift O)
3. **Use Focus Mode** (⌘K Z) - Hide UI clutter when concentration needed
4. **Terminal Integration** - Use `cmd+`` to toggle terminal for quick commands
5. **AI Pair Programming** - Use `cmd+i` for Agent mode on complex problems

---

## 🔧 Further Customization

### If You Want Even Larger Font
```json
"editor.fontSize": 18,  // Or 19-20 if 17 feels small
```

### If You Prefer Dracula Instead of Catppuccin
```json
"workbench.colorTheme": "Dracula Official",
"workbench.iconTheme": "dracula"
```
(Install: "Dracula Official" extension)

### For Terminal-Heavy Development
```json
"terminal.integrated.fontSize": 18,
"terminal.integrated.lineHeight": 1.5
```

---

## 📊 What Was Optimized

| Setting | Before | After | Why |
|---------|--------|-------|-----|
| Font Size | 19px | 17px | Better line fitting with better spacing |
| Line Height | Default | 1.6 | Reduces eye strain during long sessions |
| Letter Spacing | 0 | 0.5px | Clearer character distinction |
| Minimap | Enabled | Disabled | Cleaner sidebar, use breadcrumbs instead |
| Format on Save | ✓ | ✓ | Automatic cleanup |
| Terminal Font | 19px | 17px | Consistency with editor |
| Git Autofetch | Every 3min | Every 3min | Keeps branch status fresh |

---

## 🆘 Troubleshooting

### Text Looks Blurry
- Ensure `workbench.fontAliasing` is set to `"auto"`
- Check macOS font smoothing: System Preferences → General → Font Smoothing

### Cursor AI Not Working
- Verify you're signed into Cursor
- Try `cmd+shift+p` → "Cursor: Sign In"
- Check internet connection

### Keybindings Not Working
- Ensure you're in editor mode (click in code editor)
- `cmd+k cmd+s` opens keybindings editor
- Some keybindings may conflict with macOS (especially cmd+space)

### Performance Issues
- Check Extensions panel for resource-heavy extensions
- Try disabling minimap (already done)
- Increase `editor.maxTokenizationLineLength` in settings

---

## 📚 Useful References

- [Cursor Documentation](https://cursor.com/docs)
- [VS Code Settings Reference](https://code.visualstudio.com/docs/getstarted/settings)
- [JetBrains Mono Font](https://www.jetbrains.com/lp/mono/)
- [Catppuccin Theme](https://catppuccin.com/)

---

**Last Updated**: January 2025
**Optimized For**: 40+ Developer, MacBook Pro 2024 (M3/M4)
**Configuration Files**:
- `~/.cursor/Library/Application Support/Cursor/User/settings.json`
- `~/.cursor/Library/Application Support/Cursor/User/keybindings.json`
