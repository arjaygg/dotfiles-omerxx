#!/bin/bash
# Cursor postToolUse: delegates to advisor-escalate.py (see that file for
# the recurring-failure detection logic and schema caveats).
set -uo pipefail
/usr/bin/env python3 "$(dirname "$0")/advisor-escalate.py"
exit 0
