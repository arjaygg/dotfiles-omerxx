#!/usr/bin/env bash

# test-integration.sh - Test Charcoal + Worktrees integration
# This script verifies that all components are working correctly

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

print_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Charcoal + Worktrees Integration Test Suite           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Check if stack script exists
print_test "Checking if stack script exists..."
if [ -f "$SCRIPT_DIR/../stack" ]; then
    print_pass "Stack script found"
else
    print_fail "Stack script not found"
fi

# Test 2: Check if library files exist
print_test "Checking library files..."
if [ -f "$SCRIPT_DIR/lib/worktree-charcoal.sh" ]; then
    print_pass "worktree-charcoal.sh found"
else
    print_fail "worktree-charcoal.sh not found"
fi

if [ -f "$SCRIPT_DIR/lib/charcoal-compat.sh" ]; then
    print_pass "charcoal-compat.sh found"
else
    print_fail "charcoal-compat.sh not found"
fi

if [ -f "$SCRIPT_DIR/lib/validation.sh" ]; then
    print_pass "validation.sh found"
else
    print_fail "validation.sh not found"
fi

# Test 3: Check if libraries are executable
print_test "Checking library permissions..."
if [ -x "$SCRIPT_DIR/lib/worktree-charcoal.sh" ]; then
    print_pass "worktree-charcoal.sh is executable"
else
    print_fail "worktree-charcoal.sh is not executable"
fi

# Test 4: Check if libraries can be sourced
print_test "Testing library loading..."
if source "$SCRIPT_DIR/lib/validation.sh" 2>/dev/null; then
    print_pass "validation.sh loads successfully"
else
    print_fail "validation.sh failed to load"
fi

if source "$SCRIPT_DIR/lib/charcoal-compat.sh" 2>/dev/null; then
    print_pass "charcoal-compat.sh loads successfully"
else
    print_fail "charcoal-compat.sh failed to load"
fi

if source "$SCRIPT_DIR/lib/worktree-charcoal.sh" 2>/dev/null; then
    print_pass "worktree-charcoal.sh loads successfully"
else
    print_fail "worktree-charcoal.sh failed to load"
fi

# Test 5: Check if Charcoal is installed
print_test "Checking Charcoal installation..."
if command -v gt &> /dev/null; then
    version=$(gt --version 2>/dev/null | head -1)
    print_pass "Charcoal installed: $version"
else
    print_skip "Charcoal not installed (optional for testing)"
fi

# Test 6: Check if jq is installed
print_test "Checking jq installation..."
if command -v jq &> /dev/null; then
    version=$(jq --version 2>/dev/null)
    print_pass "jq installed: $version"
else
    print_skip "jq not installed (optional, but recommended)"
fi

# Test 7: Check if stack command works
print_test "Testing stack command..."
if "$SCRIPT_DIR/../stack" help &> /dev/null; then
    print_pass "Stack command executes successfully"
else
    print_fail "Stack command failed"
fi

# Test 8: Check documentation files
print_test "Checking documentation..."
docs=(
    "README.md"
    "INDEX.md"
    "SUMMARY.md"
    "QUICK_START.md"
    "WORKTREE_CHARCOAL_INTEGRATION.md"
    "ARCHITECTURE.md"
    "COMPARISON.md"
    "VISUAL_GUIDE.md"
)

for doc in "${docs[@]}"; do
    if [ -f "$SCRIPT_DIR/$doc" ]; then
        print_pass "$doc exists"
    else
        print_fail "$doc missing"
    fi
done

# Test 9: Check if functions are exported
print_test "Checking exported functions..."
if [ -f "$SCRIPT_DIR/lib/worktree-charcoal.sh" ]; then
    source "$SCRIPT_DIR/lib/validation.sh"
    source "$SCRIPT_DIR/lib/charcoal-compat.sh"
    source "$SCRIPT_DIR/lib/worktree-charcoal.sh"
else
    print_fail "Cannot source worktree-charcoal.sh"
    TESTS_FAILED=$((TESTS_FAILED + 8))
fi

functions=(
    "is_in_worktree"
    "get_main_repo_path"
    "get_worktree_path"
    "wt_charcoal_up"
    "wt_charcoal_down"
    "wt_charcoal_restack"
    "wt_add_for_branch"
    "wt_stack_status"
)

for func in "${functions[@]}"; do
    if declare -f "$func" &> /dev/null; then
        print_pass "Function $func is defined"
    else
        print_fail "Function $func is not defined"
    fi
done

# Test 10: Test in git repository
print_test "Testing git repository detection..."
if git rev-parse --git-dir > /dev/null 2>&1; then
    print_pass "Running in a git repository"
    
    # Test worktree detection
    if is_in_worktree; then
        print_info "Currently in a worktree"
    else
        print_info "Currently in main repository"
    fi
else
    print_skip "Not in a git repository (tests limited)"
fi

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                      Test Summary                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Tests Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Tests Failed:${NC} $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "The integration is working correctly."
    echo ""
    echo "Next steps:"
    echo "  1. Read SUMMARY.md to understand what was built"
    echo "  2. Read QUICK_START.md to get started"
    echo "  3. Try: stack init (if in a git repo)"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo ""
    echo "Please check the errors above and fix them."
    echo ""
    exit 1
fi
