#!/usr/bin/env bash
#===============================================================================
# install-hooks.sh — Pre-commit Hook Installation
#===============================================================================
#
# Installs and configures pre-commit hooks for this repository.
# Idempotent: safe to run multiple times.
#
# AUTHORITY: This script enforces CLAUDE.md governance infrastructure.
#
# REQUIREMENTS:
#   - Python 3.12+ (per DESIGN-DOC.md §5.2)
#   - pip or pipx
#
# EXIT CODES:
#   0   Success — hooks installed
#   1   Error — installation failed
#   2   Error — missing dependencies
#
# USAGE:
#   ./tools/install-hooks.sh           # Install hooks
#   ./tools/install-hooks.sh --check   # Verify installation only
#   ./tools/install-hooks.sh --help    # Display help
#
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly MIN_PYTHON_VERSION="3.10"

#===============================================================================
# COLORS
#===============================================================================

if [[ -t 1 ]] && [[ "${NO_COLOR:-}" != "1" ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[0;33m'
    readonly BLUE='\033[0;34m'
    readonly BOLD='\033[1m'
    readonly NC='\033[0m'
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly BOLD=''
    readonly NC=''
fi

#===============================================================================
# LOGGING
#===============================================================================

log_info() {
    printf "[INFO] %s\n" "$1"
}

log_success() {
    printf "${GREEN}${BOLD}[OK]${NC} ${GREEN}%s${NC}\n" "$1"
}

log_warning() {
    printf "${YELLOW}[WARN]${NC} %s\n" "$1" >&2
}

log_error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1" >&2
}

print_header() {
    printf "\n%s\n" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%s\n" "$1"
    printf "%s\n\n" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

#===============================================================================
# DEPENDENCY CHECKS
#===============================================================================

check_python() {
    log_info "Checking Python installation..."

    if ! command -v python3 &>/dev/null; then
        log_error "Python 3 not found. Install Python ${MIN_PYTHON_VERSION}+ and retry."
        return 2
    fi

    local python_version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    log_info "Found Python ${python_version}"

    # Version comparison
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
        log_error "Python ${MIN_PYTHON_VERSION}+ required. Found ${python_version}."
        return 2
    fi

    log_success "Python version OK"
    return 0
}

check_pip() {
    log_info "Checking pip installation..."

    if python3 -m pip --version &>/dev/null; then
        log_success "pip available"
        return 0
    fi

    log_error "pip not found. Install pip and retry."
    return 2
}

check_git() {
    log_info "Checking git installation..."

    if ! command -v git &>/dev/null; then
        log_warning "git not found. Hooks will be configured but not activated."
        return 1
    fi

    log_success "git available"
    return 0
}

check_git_repo() {
    log_info "Checking if inside a git repository..."

    if [[ -d "${PROJECT_ROOT}/.git" ]]; then
        log_success "Git repository detected"
        return 0
    fi

    log_warning "Not a git repository. Hooks will be configured but not activated."
    log_warning "Run 'git init' then './tools/install-hooks.sh' to activate hooks."
    return 1
}

#===============================================================================
# INSTALLATION
#===============================================================================

install_pre_commit() {
    log_info "Installing pre-commit framework..."

    if command -v pre-commit &>/dev/null; then
        local version
        version=$(pre-commit --version | awk '{print $2}')
        log_success "pre-commit already installed (${version})"
        return 0
    fi

    # Try pipx first (isolated environment, preferred)
    if command -v pipx &>/dev/null; then
        log_info "Installing via pipx..."
        pipx install pre-commit
    else
        log_info "Installing via pip..."
        python3 -m pip install --user pre-commit
    fi

    # Verify installation
    if command -v pre-commit &>/dev/null; then
        local version
        version=$(pre-commit --version | awk '{print $2}')
        log_success "pre-commit installed (${version})"
        return 0
    fi

    # Check if installed but not in PATH
    local user_bin="${HOME}/.local/bin"
    if [[ -f "${user_bin}/pre-commit" ]]; then
        log_warning "pre-commit installed but not in PATH"
        log_warning "Add to your shell profile: export PATH=\"\${HOME}/.local/bin:\${PATH}\""
        export PATH="${user_bin}:${PATH}"

        if command -v pre-commit &>/dev/null; then
            log_success "pre-commit now available"
            return 0
        fi
    fi

    log_error "pre-commit installation failed"
    return 1
}

install_hooks() {
    log_info "Installing git hooks..."

    cd "${PROJECT_ROOT}"

    # Check for config file
    if [[ ! -f ".pre-commit-config.yaml" ]]; then
        log_error ".pre-commit-config.yaml not found in project root"
        return 1
    fi

    # Install hooks
    if pre-commit install --install-hooks; then
        log_success "Pre-commit hooks installed"
    else
        log_error "Failed to install pre-commit hooks"
        return 1
    fi

    # Install commit-msg hooks (for Protocol Zero commit message validation)
    if pre-commit install --hook-type commit-msg; then
        log_success "Commit-msg hooks installed"
    else
        log_warning "Failed to install commit-msg hooks"
    fi

    return 0
}

verify_installation() {
    log_info "Verifying hook installation..."

    cd "${PROJECT_ROOT}"

    # Check hooks directory exists
    if [[ ! -d ".git/hooks" ]]; then
        log_warning ".git/hooks directory not found"
        return 1
    fi

    # Check pre-commit hook exists
    if [[ -f ".git/hooks/pre-commit" ]]; then
        log_success "pre-commit hook installed"
    else
        log_warning "pre-commit hook not found"
        return 1
    fi

    # Check commit-msg hook exists
    if [[ -f ".git/hooks/commit-msg" ]]; then
        log_success "commit-msg hook installed"
    else
        log_warning "commit-msg hook not found"
    fi

    return 0
}

run_validation() {
    log_info "Running pre-commit validation..."

    cd "${PROJECT_ROOT}"

    # Run hooks on all files to validate configuration
    if pre-commit run --all-files; then
        log_success "All hooks passed"
        return 0
    else
        log_warning "Some hooks failed — this is expected on first run"
        log_warning "Fix issues and commit to establish baseline"
        return 0
    fi
}

#===============================================================================
# HELP
#===============================================================================

print_usage() {
    cat << EOF
${BOLD}Pre-commit Hook Installation${NC}

${BOLD}USAGE${NC}
    ./tools/install-hooks.sh [OPTIONS]

${BOLD}OPTIONS${NC}
    --check     Verify installation without making changes
    --validate  Run hooks on all files after installation
    --help, -h  Display this help message

${BOLD}DESCRIPTION${NC}
    Installs and configures pre-commit hooks for this repository.
    This script is idempotent and safe to run multiple times.

${BOLD}REQUIREMENTS${NC}
    - Python ${MIN_PYTHON_VERSION}+
    - pip or pipx
    - git (optional, for hook activation)

${BOLD}WHAT GETS INSTALLED${NC}
    1. pre-commit framework (via pipx or pip)
    2. Git hooks:
       - pre-commit: Protocol Zero, Ruff, SQLFluff, sqlfmt
       - commit-msg: Protocol Zero commit message validation

${BOLD}MANUAL EXECUTION${NC}
    After installation, you can run hooks manually:

    pre-commit run --all-files     # Run all hooks on all files
    pre-commit run protocol-zero   # Run specific hook
    pre-commit run --files <file>  # Run on specific file

${BOLD}BYPASS (emergency only)${NC}
    git commit --no-verify -m "message"

EOF
}

#===============================================================================
# MAIN
#===============================================================================

main() {
    local check_only=0
    local validate=0

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --check)
                check_only=1
                shift
                ;;
            --validate)
                validate=1
                shift
                ;;
            --help|-h)
                print_usage
                return 0
                ;;
            *)
                log_warning "Unknown argument: $1"
                shift
                ;;
        esac
    done

    print_header "Pre-commit Hook Installation"

    # Change to project root
    cd "${PROJECT_ROOT}"

    # Check dependencies
    check_python || return $?
    check_pip || return $?

    local has_git=0
    local is_git_repo=0

    if check_git; then
        has_git=1
    fi

    if [[ ${has_git} -eq 1 ]] && check_git_repo; then
        is_git_repo=1
    fi

    # Check-only mode
    if [[ ${check_only} -eq 1 ]]; then
        log_info "Check-only mode"

        if command -v pre-commit &>/dev/null; then
            log_success "pre-commit is installed"
        else
            log_warning "pre-commit is not installed"
            return 1
        fi

        if [[ ${is_git_repo} -eq 1 ]]; then
            verify_installation
        fi

        return 0
    fi

    # Install pre-commit
    install_pre_commit || return $?

    # Install hooks if git repo exists
    if [[ ${is_git_repo} -eq 1 ]]; then
        install_hooks || return $?
        verify_installation
    else
        log_info "Skipping hook installation (no git repository)"
        log_info "Run 'git init && ./tools/install-hooks.sh' to activate hooks"
    fi

    # Optionally validate
    if [[ ${validate} -eq 1 ]] && [[ ${is_git_repo} -eq 1 ]]; then
        printf "\n"
        run_validation
    fi

    printf "\n"
    print_header "Installation Complete"
    log_success "Pre-commit hooks are now configured"

    if [[ ${is_git_repo} -eq 1 ]]; then
        log_info "Hooks will run automatically on: git commit"
        log_info "Manual run: pre-commit run --all-files"
    else
        log_info "Initialize git and re-run to activate: git init && ./tools/install-hooks.sh"
    fi

    printf "\n"
    return 0
}

main "$@"
