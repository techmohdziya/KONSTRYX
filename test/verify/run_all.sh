#!/usr/bin/env bash
# Runs every verification suite against a freshly started service, so no suite
# inherits another's data. H2 is in-memory, so a restart is a clean database.
set -u
SP="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SP/../.." && pwd)"
RESULTS="$SP/results.txt"
: "${JAVA_HOME:=/c/Program Files/SapMachine/JDK/17}"
export JAVA_HOME

# No outbound S/4, ever, from a verification run. Release posts to S/4 as soon
# as a project is released, and S4Connection will happily pick up credentials
# from a developer's .env - which is how a test run started creating projects in
# a live tenant. Suites assert the queued outcome; this is what makes that the
# outcome regardless of whose machine it runs on.
export S4_OFFLINE=true

SUITES="test_foundations test_content test_approval test_persona_approver test_attachments test_variants test_project test_schedule test_p6 test_rates test_boq test_chain test_planning test_budget test_distribution test_procurement test_certification"

: > "$RESULTS"

stop() {
  taskkill //F //IM java.exe >/dev/null 2>&1
  sleep 2
}

start() {
  rm -f "$SP/kx.log"
  ( cd "$ROOT" && nohup "$JAVA_HOME/bin/java" -jar srv/target/konstryx-srv-exec.jar > "$SP/kx.log" 2>&1 & )
  local n=0
  until grep -qE "Content pack NUMBER_RANGES|APPLICATION FAILED" "$SP/kx.log" 2>/dev/null; do
    sleep 1; n=$((n+1))
    if [ $n -gt 60 ]; then return 1; fi
  done
  sleep 2
  return 0
}

for suite in $SUITES; do
  stop
  if ! start; then
    echo "$suite|START-FAILED|0|0" >> "$RESULTS"
    continue
  fi
  out=$(python "$SP/$suite.py" 2>&1)
  echo "$out" > "$SP/out_$suite.txt"
  line=$(echo "$out" | grep -E "^  [0-9]+ of [0-9]+ checks passed" | tail -1)
  if [ -z "$line" ]; then
    echo "$suite|CRASHED|0|0" >> "$RESULTS"
  else
    p=$(echo "$line" | awk '{print $1}')
    t=$(echo "$line" | awk '{print $3}')
    if [ "$p" = "$t" ]; then echo "$suite|PASS|$p|$t" >> "$RESULTS"
    else echo "$suite|FAIL|$p|$t" >> "$RESULTS"; fi
  fi
done

echo "DONE" >> "$RESULTS"
