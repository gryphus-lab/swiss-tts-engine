#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Unit tests for dev.sh
#
# Tests the OS-detection and HOST_IP-resolution logic without side effects.
# Each test runs the relevant subset of dev.sh in a sub-shell that overrides
# external commands (uname, ipconfig, ip, hostname, mise) with stubs.
#
# Usage (from repo root):
#   bash tests/dev_sh_test.sh
# ---------------------------------------------------------------------------

set -euo pipefail

PASS=0
FAIL=0
TOTAL=0

# Path to dev.sh relative to the repo root (this script lives in tests/)
DEV_SH="$(cd "$(dirname "$0")/.." && pwd)/dev.sh"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

assert_eq() {
    local description="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [ "$expected" = "$actual" ]; then
        echo "  PASS: $description"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $description"
        echo "        expected: '$expected'"
        echo "        actual:   '$actual'"
        FAIL=$((FAIL + 1))
    fi
}

assert_exit_code() {
    local description="$1" expected_code="$2" actual_code="$3"
    TOTAL=$((TOTAL + 1))
    if [ "$expected_code" = "$actual_code" ]; then
        echo "  PASS: $description"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $description"
        echo "        expected exit code: $expected_code"
        echo "        actual exit code:   $actual_code"
        FAIL=$((FAIL + 1))
    fi
}

assert_output_contains() {
    local description="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qF "$needle"; then
        echo "  PASS: $description"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $description"
        echo "        expected output to contain: '$needle'"
        echo "        actual output: '$haystack'"
        FAIL=$((FAIL + 1))
    fi
}

# ---------------------------------------------------------------------------
# run_logic <uname_val> <ipconfig_val> <ip_route_val> <hostname_I_val>
#
# Runs the OS-detection + HOST_IP-validation section of dev.sh inside a
# fresh sub-shell with all external commands stubbed out.
#
# Arguments:
#   $1  value returned by uname
#   $2  value returned by ipconfig getifaddr en0 (macOS path)
#   $3  IP address embedded in "ip route" output (Linux path); "" → command fails
#   $4  value returned by "hostname -I" (Linux fallback)
#
# Exits with the same code as the logic block.
# Prints "HOST_IP=<value>" and "OS=<value>" on success.
# ---------------------------------------------------------------------------

run_logic() {
    local _uname="$1"
    local _ipconfig="$2"
    local _ip_route="$3"
    local _hostname_i="$4"

    # Everything runs inside a sub-shell so stubs never leak.
    (
        uname()    { echo "$_uname"; }
        ipconfig() { echo "$_ipconfig"; }          # ipconfig getifaddr en0
        ip()       {                                # ip route get 1.0.0.1
            if [ -n "$_ip_route" ]; then
                echo "1.0.0.1 via 192.168.1.1 dev eth0 src ${_ip_route} uid 1000"
            else
                return 1
            fi
        }
        hostname() { echo "$_hostname_i"; }        # hostname -I
        mise()     { :; }                           # no-op – prevent Docker calls

        OS="$(uname)"

        if [ "$OS" = "Darwin" ]; then
            HOST_IP=$(ipconfig getifaddr en0)
        elif [ "$OS" = "Linux" ]; then
            HOST_IP=$(ip route get 1.0.0.1 2>/dev/null | awk '{print $7; exit}' \
                      || hostname -I | awk '{print $1}')
        else
            echo "❌ Unsupported OS environment. Please set HOST_IP manually."
            exit 1
        fi

        if [ -z "$HOST_IP" ]; then
            echo "❌ Could not automatically detect your local IP address."
            echo "Ensure you are connected to Wi-Fi/LAN."
            exit 1
        fi

        echo "HOST_IP=$HOST_IP"
        echo "OS=$OS"
    )
}

# Capture output + exit code without triggering set -e.
# Usage: capture_run <output_var> <exit_var> <args...>
capture_run() {
    local _out_var="$1" _exit_var="$2"
    shift 2
    local _out _rc=0
    if _out=$(run_logic "$@" 2>&1); then
        _rc=0
    else
        _rc=$?
    fi
    printf -v "$_out_var" '%s' "$_out"
    printf -v "$_exit_var" '%s' "$_rc"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

echo "=== dev.sh unit tests ==="
echo ""

# ---------------------------------------------------------------------------
# macOS (Darwin)
# ---------------------------------------------------------------------------

echo "-- macOS (Darwin) OS detection --"

capture_run out rc "Darwin" "10.0.0.5" "" ""
assert_eq "Darwin: HOST_IP is set from ipconfig output" \
    "HOST_IP=10.0.0.5" "$(echo "$out" | grep '^HOST_IP=')"
assert_eq "Darwin: OS variable is Darwin" \
    "OS=Darwin"   "$(echo "$out" | grep '^OS=')"
assert_exit_code "Darwin: exits with code 0 on success" "0" "$rc"

# Boundary: different IP address
capture_run out rc "Darwin" "172.16.0.1" "" ""
assert_eq "Darwin: handles a 172.x.x.x IP" \
    "HOST_IP=172.16.0.1" "$(echo "$out" | grep '^HOST_IP=')"

# ---------------------------------------------------------------------------
# Linux – primary path via ip route
# ---------------------------------------------------------------------------

echo ""
echo "-- Linux OS detection (ip route) --"

capture_run out rc "Linux" "" "192.168.0.99" ""
assert_eq "Linux: HOST_IP is set from ip route output" \
    "HOST_IP=192.168.0.99" "$(echo "$out" | grep '^HOST_IP=')"
assert_eq "Linux: OS variable is Linux" \
    "OS=Linux" "$(echo "$out" | grep '^OS=')"
assert_exit_code "Linux (ip route): exits with code 0 on success" "0" "$rc"

# ---------------------------------------------------------------------------
# Linux – fallback to hostname -I when ip route fails
# ---------------------------------------------------------------------------

echo ""
echo "-- Linux OS detection (hostname -I fallback) --"

capture_run out rc "Linux" "" "" "10.10.10.10"
assert_eq "Linux: HOST_IP falls back to hostname -I when ip route fails" \
    "HOST_IP=10.10.10.10" "$(echo "$out" | grep '^HOST_IP=')"
assert_exit_code "Linux (hostname -I): exits with code 0 on success" "0" "$rc"

# hostname -I can return multiple IPs; awk picks the first
capture_run out rc "Linux" "" "" "10.10.10.10 10.10.10.11"
assert_eq "Linux: hostname -I with multiple IPs – first one is used" \
    "HOST_IP=10.10.10.10" "$(echo "$out" | grep '^HOST_IP=')"

# ---------------------------------------------------------------------------
# Unsupported OS
# ---------------------------------------------------------------------------

echo ""
echo "-- Unsupported OS --"

capture_run out rc "Windows_NT" "" "" ""
assert_exit_code "Unsupported OS: exits with code 1" "1" "$rc"
assert_output_contains "Unsupported OS: error message mentions unsupported environment" \
    "Unsupported OS environment" "$out"

# Regression: the error message should NOT mention "HOST_IP" or suggest Docker
capture_run out rc "FreeBSD" "" "" ""
assert_exit_code "Other unsupported OS (FreeBSD): exits with code 1" "1" "$rc"
assert_output_contains "Other unsupported OS: tells user to set HOST_IP manually" \
    "Please set HOST_IP manually" "$out"

# ---------------------------------------------------------------------------
# Empty HOST_IP (no network interface / no Wi-Fi)
# ---------------------------------------------------------------------------

echo ""
echo "-- Empty HOST_IP fallback --"

# macOS: ipconfig returns nothing (e.g. no Wi-Fi interface)
capture_run out rc "Darwin" "" "" ""
assert_exit_code "Darwin empty HOST_IP: exits with code 1" "1" "$rc"
assert_output_contains "Darwin empty HOST_IP: error mentions IP detection failure" \
    "Could not automatically detect" "$out"
assert_output_contains "Darwin empty HOST_IP: error mentions Wi-Fi/LAN" \
    "Wi-Fi/LAN" "$out"

# Linux: both ip route and hostname -I return nothing
capture_run out rc "Linux" "" "" ""
assert_exit_code "Linux empty HOST_IP: exits with code 1" "1" "$rc"
assert_output_contains "Linux empty HOST_IP: error mentions IP detection failure" \
    "Could not automatically detect" "$out"

# ---------------------------------------------------------------------------
# dev.sh file-level checks (regression guards)
# ---------------------------------------------------------------------------

echo ""
echo "-- dev.sh file checks --"

TOTAL=$((TOTAL + 1))
if [ -f "$DEV_SH" ]; then
    echo "  PASS: dev.sh exists at expected path"
    PASS=$((PASS + 1))
else
    echo "  FAIL: dev.sh not found at $DEV_SH"
    FAIL=$((FAIL + 1))
fi

TOTAL=$((TOTAL + 1))
if [ -x "$DEV_SH" ]; then
    echo "  PASS: dev.sh is executable"
    PASS=$((PASS + 1))
else
    echo "  FAIL: dev.sh is not executable (missing +x permission)"
    FAIL=$((FAIL + 1))
fi

TOTAL=$((TOTAL + 1))
if grep -q 'set -euo pipefail' "$DEV_SH"; then
    echo "  PASS: dev.sh uses 'set -euo pipefail'"
    PASS=$((PASS + 1))
else
    echo "  FAIL: dev.sh missing 'set -euo pipefail'"
    FAIL=$((FAIL + 1))
fi

# The script must delegate Docker startup to mise, not call docker directly
TOTAL=$((TOTAL + 1))
if grep -q 'mise run docker-compose' "$DEV_SH"; then
    echo "  PASS: dev.sh delegates Docker startup to 'mise run docker-compose'"
    PASS=$((PASS + 1))
else
    echo "  FAIL: dev.sh does not call 'mise run docker-compose'"
    FAIL=$((FAIL + 1))
fi

# The script must stream logs via mise
TOTAL=$((TOTAL + 1))
if grep -q 'mise run docker-app-logs' "$DEV_SH"; then
    echo "  PASS: dev.sh streams logs via 'mise run docker-app-logs'"
    PASS=$((PASS + 1))
else
    echo "  FAIL: dev.sh does not call 'mise run docker-app-logs'"
    FAIL=$((FAIL + 1))
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi