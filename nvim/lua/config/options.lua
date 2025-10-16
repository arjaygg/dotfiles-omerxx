-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

-- Font configuration
vim.opt.guifont = "JetBrains Mono:h16"

-- Text wrapping
vim.opt.wrap = true

-- Codeium configuration
vim.g.codeium_os = "Darwin"
vim.g.codeium_arch = "arm64"

-- Additional productivity settings
vim.opt.relativenumber = true
vim.opt.cursorline = true
vim.opt.scrolloff = 8
vim.opt.sidescrolloff = 8
