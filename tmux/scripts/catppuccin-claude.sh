show_claude() {
  local index=$1
  local icon="$(get_tmux_option "@catppuccin_claude_icon" "")"
  local color="$(get_tmux_option "@catppuccin_claude_color" "$thm_mauve")"

  # Read pane-level Claude state
  local status="$(tmux display-message -p '#{@claude_status}' 2>/dev/null)"

  # No active Claude session → show nothing
  if [[ -z "$status" ]]; then
    echo ""
    return
  fi

  local project="$(tmux display-message -p '#{@claude_project}' 2>/dev/null)"
  local branch="$(tmux display-message -p '#{@claude_branch}' 2>/dev/null)"

  local text=""
  if [[ "$status" == "working" ]]; then
    text=" ${project}"
  else
    text="${project}"
  fi

  if [[ -n "$branch" ]]; then
    text="${text}[${branch}]"
  fi

  local module=$(build_status_module "$index" "$icon" "$color" "$text")

  echo "$module"
}
