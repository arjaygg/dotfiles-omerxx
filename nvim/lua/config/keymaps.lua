-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here
vim.api.nvim_set_keymap("i", "jj", "<Esc>", { noremap = false })
vim.api.nvim_set_keymap("i", "jk", "<Esc>", { noremap = false })

-- Copy absolute path to system clipboard. Use <leader>fy, not <leader>cp:
-- lazyvim.plugins.extras.lang.markdown binds <leader>cp to Markdown Preview.
--
-- setreg("+") alone can fail when +clipboard is missing, in SSH (LazyVim clears
-- unnamedplus), or in some hosts; fall back to pbcopy/xclip/wl-copy.
local function copy_to_clipboard(text)
  if vim.fn.has("clipboard") == 1 then
    vim.fn.setreg("+", text)
    vim.fn.setreg("*", text)
  end
  if vim.fn.executable("pbcopy") == 1 then
    vim.fn.system("pbcopy", text)
  elseif vim.fn.executable("xclip") == 1 then
    vim.fn.system({ "xclip", "-selection", "clipboard" }, text)
  elseif vim.fn.executable("wl-copy") == 1 then
    vim.fn.system({ "wl-copy" }, text)
  end
end

vim.keymap.set("n", "<leader>fy", function()
  local path = vim.fn.expand("%:p")
  if path == "" or path:match("^%s*$") then
    vim.notify("No file path on disk", vim.log.levels.WARN)
    return
  end
  -- Defer so clipboard runs after LazyVim restores opt.clipboard on VeryLazy.
  vim.schedule(function()
    copy_to_clipboard(path)
    vim.notify("Copied absolute path")
  end)
end, { desc = "Copy absolute file path" })
