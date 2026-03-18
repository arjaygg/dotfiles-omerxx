---
name: install_yazi
overview: Replace ranger with yazi in Brewfile, install yazi, and configure Nushell integration.
todos: []
---

# Switch from Ranger to Yazi

1.  **Update Brewfile**

    - Remove `brew "ranger"`
    - Add `brew "yazi"`
    - Add dependencies: `brew "ffmpeg"`, `brew "sevenzip"`, `brew "jq"`

2.  **Configure Nushell**

    - Add `y` wrapper function to `nushell/config.nu` for CD-on-exit functionality.

3.  **Install Packages**

    - Run `brew install yazi ffmpeg sevenzip jq` to install the new tools immediately.
    - (Optional) Run `brew uninstall ranger` if it was installed (it wasn't, but good for cleanup if it was).