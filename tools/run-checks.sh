#!/usr/bin/env bash
#===============================================================================
# run-checks.sh — Manual Check Runner
#===============================================================================
#
# Runs all pre-commit checks manually without requiring git.
# Useful for CI, local validation, or when git is not yet initialized.
#
# AUTHORITY: This script provides manual access to CLAUDE.md enforcement.
#
# EXIT CODES:
#   0   All checks passed
#   1   One or more checks failed
#   2   Configuration error
#
# USAGE:
#   ./tools/run-checks.sh                  # Run all checks
#   ./tools/run-checks.sh --quick          # Fast checks only (no type check)
#   ./tools/run-checks.sh --protocol-zero  # Protocol Zero only
#   ./tools/run-checks.sh --python         # Python checks only
#   ./tools/run-checks.sh --sql            # SQL checks only
#   ./tools/run-checks.sh --help           # Display help
#
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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
    printf "${GREEN}${BOLD}[PASS]${NC} ${GREEN}%s${NC}\n" "$1"
}

log_fail() {
    printf "${RED}${BOLD}[FAIL]${NC} ${RED}%s${NC}\n" "$1"
}

log_skip() {
    printf "${YELLOW}[SKIP]${NC} %s\n" "$1"
}

print_header() {
    printf "\n%s\n" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%s\n" "$1"
    printf "%s\n\n" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

#===============================================================================
# CHECK FUNCTIONS
#===============================================================================

FAILURES=0

run_check() {
    local name="$1"
    local cmd="$2"

    printf "${BLUE}▶${NC} Running: %s\n" "${name}"

    if eval "${cmd}"; then
        log_success "${name}"
        return 0
    else
        log_fail "${name}"
        ((FAILURES++)) || true
        return 1
    fi
}

check_protocol_zero() {
    run_check "Protocol Zero: Codebase Scan" \
        "${SCRIPT_DIR}/protocol-zero.sh"
}

check_python_ruff_lint() {
    if [[ ! -d "${PROJECT_ROOT}/scripts" ]]; then
        log_skip "Ruff lint (no scripts/ directory)"
        return 0
    fi

    if ! command -v ruff &>/dev/null; then
        log_skip "Ruff lint (ruff not installed)"
        return 0
    fi

    run_check "Ruff: Python Lint" \
        "ruff check ${PROJECT_ROOT}/scripts/ --select=E,F,W,I,UP,B,C4,SIM --ignore=E501"
}

check_python_ruff_format() {
    if [[ ! -d "${PROJECT_ROOT}/scripts" ]]; then
        log_skip "Ruff format (no scripts/ directory)"
        return 0
    fi

    if ! command -v ruff &>/dev/null; then
        log_skip "Ruff format (ruff not installed)"
        return 0
    fi

    run_check "Ruff: Python Format Check" \
        "ruff format --check ${PROJECT_ROOT}/scripts/"
}

check_python_mypy() {
    if [[ ! -d "${PROJECT_ROOT}/scripts" ]]; then
        log_skip "mypy (no scripts/ directory)"
        return 0
    fi

    if ! command -v mypy &>/dev/null; then
        log_skip "mypy (mypy not installed)"
        return 0
    fi

    run_check "mypy: Type Check" \
        "mypy ${PROJECT_ROOT}/scripts/ --strict --ignore-missing-imports"
}

check_sql_sqlfmt() {
    if [[ ! -d "${PROJECT_ROOT}/models" ]]; then
        log_skip "sqlfmt (no models/ directory)"
        return 0
    fi

    if ! command -v sqlfmt &>/dev/null; then
        log_skip "sqlfmt (sqlfmt not installed)"
        return 0
    fi

    run_check "sqlfmt: SQL Format Check" \
        "sqlfmt --check --diff ${PROJECT_ROOT}/models/ --exclude 'target/**/*' --exclude 'dbt_packages/**/*'"
}

check_sql_sqlfluff() {
    if [[ ! -d "${PROJECT_ROOT}/models" ]]; then
        log_skip "SQLFluff (no models/ directory)"
        return 0
    fi

    if ! command -v sqlfluff &>/dev/null; then
        log_skip "SQLFluff (sqlfluff not installed)"
        return 0
    fi

    run_check "SQLFluff: SQL Lint" \
        "sqlfluff lint ${PROJECT_ROOT}/models/ --dialect snowflake"
}

check_shell() {
    if ! command -v shellcheck &>/dev/null; then
        log_skip "ShellCheck (shellcheck not installed)"
        return 0
    fi

    run_check "ShellCheck: Shell Lint" \
        "shellcheck -x ${SCRIPT_DIR}/*.sh"
}

#===============================================================================
# HELP
#===============================================================================

print_usage() {
    cat << EOF
${BOLD}Manual Check Runner${NC}

${BOLD}USAGE${NC}
    ./tools/run-checks.sh [OPTIONS]

${BOLD}OPTIONS${NC}
    --all            Run all checks (default)
    --quick          Fast checks only (skip type checking)
    --protocol-zero  Protocol Zero scan only
    --python         Python checks only (ruff, mypy)
    --sql            SQL checks only (sqlfmt, sqlfluff)
    --shell          Shell script checks only
    --help, -h       Display this help

${BOLD}DESCRIPTION${NC}
    Runs pre-commit checks without requiring git or pre-commit framework.
    Useful for CI pipelines, local validation, or pre-git-init development.

${BOLD}EXIT CODES${NC}
    0   All checks passed
    1   One or more checks failed
    2   Configuration error

${BOLD}EXAMPLES${NC}
    ./tools/run-checks.sh                  # Full suite
    ./tools/run-checks.sh --quick          # Fast feedback
    ./tools/run-checks.sh --protocol-zero  # Attribution scan only

EOF
}

#===============================================================================
# MAIN
#===============================================================================

main() {
    local mode="all"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all)
                mode="all"
                shift
                ;;
            --quick)
                mode="quick"
                shift
                ;;
            --protocol-zero)
                mode="protocol-zero"
                shift
                ;;
            --python)
                mode="python"
                shift
                ;;
            --sql)
                mode="sql"
                shift
                ;;
            --shell)
                mode="shell"
                shift
                ;;
            --help|-h)
                print_usage
                return 0
                ;;
            *)
                log_info "Unknown argument: $1"
                shift
                ;;
        esac
    done

    print_header "Running Checks: ${mode}"

    cd "${PROJECT_ROOT}"

    case "${mode}" in
        all)
            check_protocol_zero
            check_python_ruff_lint
            check_python_ruff_format
            check_python_mypy
            check_sql_sqlfmt
            check_sql_sqlfluff
            check_shell
            ;;
        quick)
            check_protocol_zero
            check_python_ruff_lint
            check_python_ruff_format
            check_shell
            ;;
        protocol-zero)
            check_protocol_zero
            ;;
        python)
            check_python_ruff_lint
            check_python_ruff_format
            check_python_mypy
            ;;
        sql)
            check_sql_sqlfmt
            check_sql_sqlfluff
            ;;
        shell)
            check_shell
            ;;
    esac

    printf "\n"
    print_header "Summary"

    if [[ ${FAILURES} -eq 0 ]]; then
        log_success "All checks passed"
        return 0
    else
        log_fail "${FAILURES} check(s) failed"
        return 1
    fi
}

main "$@"
