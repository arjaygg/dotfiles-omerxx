#!/usr/bin/env bash
# Git credential helper that always uses the axosEnt GitHub Enterprise account.
# Prevents "Repository not found" errors when the active gh account is personal.
# Usage: git config credential."https://github.com".helper "!~/.dotfiles/git/scripts/gh-enterprise-credential.sh"

ENT_USER="Arjay-Gallentes_axosEnt"

case "$1" in
  get)
    cat /dev/stdin > /dev/null  # consume required input
    token=$(gh auth token --user "$ENT_USER" 2>/dev/null)
    if [[ -n "$token" ]]; then
      echo "username=$ENT_USER"
      echo "password=$token"
    fi
    ;;
  store|erase)
    cat /dev/stdin > /dev/null
    ;;
esac
