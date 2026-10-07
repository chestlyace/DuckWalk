#!/usr/bin/env bash
# Failure drill: stop Ollama in the middle of a WalkSession, bring it back, and
# confirm the session still completes, with the LLM retries visible in history.
#
#   bash scripts/drill_ollama_kill.sh            # Ollama down for 10s (default)
#   DOWN_S=20 bash scripts/drill_ollama_kill.sh
#
# Needs sudo (Ollama runs as a system service) and the duckwalk systemd services.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DOWN_S="${DOWN_S:-10}"
S=".venv/bin/python -m duckwalk.workflows.starter"
step() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

sudo -v  # ask for the password up front, not mid-drill

step "Starting a WalkSession (failing_test fixture)"
id=$($S trigger --fixture failing_test)
echo "$id"
for _ in $(seq 60); do
  st=$($S status "$id")
  case "$st" in
    *waiting_for_movement*) break ;;
    *FAILED*|*COMPLETED*|*TERMINATED*|*CANCELED*|*TIMED_OUT*)
      echo "$st"; echo "Session ended before the drill began (is Ollama or the worker healthy?). Aborting." >&2; exit 1 ;;
  esac
  sleep 1
done
case "$st" in *waiting_for_movement*) ;; *) echo "Timed out waiting for the session to reach the movement wait: $st" >&2; exit 1 ;; esac
echo "$st"

step "Stopping Ollama"
sudo systemctl stop ollama
step "Phone starts moving -> voice loop -> brief (LLM call fails while Ollama is down)"
$S signal "$id"
sleep "$DOWN_S"
$S status "$id"

step "Starting Ollama after ${DOWN_S}s"
sudo systemctl start ollama

step "Waiting for the session to finish"
$S result "$id"

step "Activity attempts from workflow history"
vendor/bin/temporal workflow show -w "$id" --output json | .venv/bin/python -c '
import json, sys
hist = json.load(sys.stdin)
events = hist.get("events", hist)
names = {}
for e in events:
    attrs = e.get("activityTaskScheduledEventAttributes")
    if attrs:
        names[e["eventId"]] = attrs["activityType"]["name"]
retried = False
for e in events:
    attrs = e.get("activityTaskStartedEventAttributes")
    if attrs:
        name, attempt = names[attrs["scheduledEventId"]], attrs.get("attempt", 1)
        failure = attrs.get("lastFailure", {}).get("message", "")
        retried |= attempt > 1
        print(f"  {name:<20} attempt {attempt}" + (f"   last failure: {failure[:90]}" if failure else ""))
status = events[-1]["eventType"]
print(f"\n  final event: {status}")
ok = retried and status.endswith("COMPLETED")
print("  DRILL PASSED: Ollama was killed, Temporal retried, and the session completed." if ok
      else "  DRILL FAILED: expected a retried activity and a completed workflow.")
sys.exit(0 if ok else 1)
'
echo
echo "Temporal UI: http://localhost:8233/namespaces/default/workflows/$id"
