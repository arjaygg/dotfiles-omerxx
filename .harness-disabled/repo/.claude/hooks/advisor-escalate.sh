#!/bin/bash
# Claude Code PostToolUse: delegates to advisor-escalate.py (see that file for
# the recurring-failure detection logic and rationale — backstop for the
# native advisor tool going silent on long transcripts).
set -uo pipefail
/usr/bin/env python3 "$(dirname "$0")/advisor-escalate.py"
exit 0
