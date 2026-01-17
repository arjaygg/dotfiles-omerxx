# PR Stack Library

Shared utilities and validation functions for PR stacking scripts.

## Files

- `validation.sh` - Validation functions for PR stacking operations

## Usage in Scripts

```bash
#!/bin/bash

# Load validation library at the top of your script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"

# Now you can use validation functions
validate_git_repository || exit 1
validate_branch_exists "main" || exit 1
```

## Available Functions

### Core Validation

- `validate_git_repository()` - Check if in a git repository
- `validate_branch_name(name)` - Validate branch name format
- `validate_branch_exists(name)` - Check if branch exists
- `validate_branch_not_exists(name)` - Check if branch doesn't exist
- `validate_remote_branch_exists(name, [remote])` - Check if remote branch exists
- `validate_azure_cli()` - Check if Azure CLI is installed

### Stack-Specific Validation

- `is_stacking_active()` - Check if PR stacking is being used
- `validate_stack_info_exists()` - Check if stack info file exists
- `get_stack_base_branch(branch)` - Get the base branch for a stacked branch
- `validate_stack_integrity(branch)` - Validate branch is in sync with base
- `validate_pr_target(source, target)` - Validate PR target is correct

### Helper Functions

- `get_repo_root()` - Get repository root directory
- `is_at_repo_root()` - Check if at repository root
- `ensure_repo_root()` - CD to repository root
- `is_working_directory_clean()` - Check for uncommitted changes
- `warn_if_dirty_working_directory()` - Warn about uncommitted changes

### Compound Validation

- `validate_common_prerequisites()` - Validate git repo and CD to root
- `validate_stack_create_prerequisites(new, base)` - Validate branch creation
- `validate_pr_create_prerequisites(source, target)` - Validate PR creation
- `validate_stack_update_prerequisites()` - Validate stack update

### Print Functions

- `print_error(message)` - Print error message in red
- `print_success(message)` - Print success message in green
- `print_info(message)` - Print info message in blue
- `print_warning(message)` - Print warning message in yellow

## Design Principles

### 1. Opt-in Detection

Validation only applies when PR stacking is detected:

```bash
if is_stacking_active; then
    # Run stack-specific validation
    validate_stack_integrity "$branch" || exit 1
else
    # Traditional workflow - skip validation
    echo "Not using stacking, skipping checks"
fi
```

### 2. Non-Disruptive

- Traditional workflows are unaffected
- Warnings are non-blocking (unless critical)
- Clear error messages with fix instructions

### 3. DRY Principle

- Validation logic in one place
- Reusable across all scripts
- Easy to maintain and update

## Examples

### Example 1: Basic Validation

```bash
#!/bin/bash
source "$(dirname "$0")/lib/validation.sh"

# Validate common prerequisites
validate_common_prerequisites || exit 1

# Validate branch
validate_branch_exists "main" || exit 1

echo "All validations passed!"
```

### Example 2: Stack-Aware Validation

```bash
#!/bin/bash
source "$(dirname "$0")/lib/validation.sh"

BRANCH="feature/api"

# Only validate if stacking is active
if is_stacking_active; then
    print_info "Stacking detected, validating..."
    validate_stack_integrity "$BRANCH" || exit 1
else
    print_info "Traditional workflow, skipping stack validation"
fi
```

### Example 3: PR Creation with Validation

```bash
#!/bin/bash
source "$(dirname "$0")/lib/validation.sh"

SOURCE="feature/api"
TARGET="feature/db"

# Validate prerequisites
validate_pr_create_prerequisites "$SOURCE" "$TARGET" || exit 1

# Validate target (non-blocking warning)
validate_pr_target "$SOURCE" "$TARGET" || {
    print_warning "Target validation failed, but continuing..."
}

# Create PR
echo "Creating PR from $SOURCE to $TARGET..."
```

## Testing

Test the validation library:

```bash
# From repository root
cd scripts/pr-stack

# Test validation functions
bash -c "source lib/validation.sh && validate_git_repository && echo '✓ Git repo check passed'"
bash -c "source lib/validation.sh && validate_branch_exists main && echo '✓ Branch exists'"
bash -c "source lib/validation.sh && is_stacking_active && echo '✓ Stacking active' || echo 'ℹ️ Stacking not active'"
```

## Maintenance

When adding new validation:

1. Add function to `validation.sh`
2. Export function at bottom of file
3. Document in this README
4. Test with existing scripts
5. Update scripts to use new validation

## Error Handling

All validation functions follow this pattern:

```bash
validate_something() {
    if [ condition_fails ]; then
        print_error "What went wrong"
        print_info "How to fix it"
        return 1
    fi
    return 0
}
```

Usage in scripts:

```bash
# Exit on failure
validate_something || exit 1

# Continue on failure
validate_something || {
    print_warning "Validation failed but continuing..."
}

# Custom error handling
if ! validate_something; then
    echo "Custom error handling"
    exit 1
fi
```
