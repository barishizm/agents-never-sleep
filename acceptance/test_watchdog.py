#!/usr/bin/env python3
"""Watchdog test — proves the heartbeat sidecar that catches a HANG (the gap the Stop-hook can't see).

The Stop-hook blocks a premature stop but cannot tell a hung run from a working one. The watchdog
runs the unattended command as a child, polls its heartbeat, restarts it resumable when the heartbeat
goes stale, and on exhausted restarts runs an alert and exits 75 (claude-run's "gave up" convention).
This proves all three hermetically with bounded fake children — NO live claude-run is touched (the
watchdog is a sidecar by design; integrating with claude-run is opt-in composition, never a rewrite).

Exit 0 = GREEN.
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep import watchdog  # noqa: E402

PY = sys.executable


def _hb(path, ts):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"ts": ts, "n": 1, "ticket": "", "phase": ""}, fh)


def test_child_exits_clean(failures, tmp):
    """A child that finishes on its own → watchdog returns the child's exit code, no restart."""
    hb = os.path.join(tmp, "hb1.json")
    rc = watchdog.main(["--heartbeat", hb, "--stale", "30", "--poll", "1", "--grace", "0",
                        "--max-restarts", "1", "--", PY, "-c", "import sys; sys.exit(0)"])
    if rc != 0:
        failures.append(f"[clean-exit] expected child rc 0 passthrough, got {rc}")


def test_fresh_heartbeat_no_restart(failures, tmp):
    """A child whose heartbeat stays fresh must NOT be restarted — it runs to its own clean exit."""
    hb = os.path.join(tmp, "hb2.json")
    _hb(hb, time.time())  # fresh; stale=30 >> child lifetime so age never exceeds it
    rc = watchdog.main(["--heartbeat", hb, "--stale", "30", "--poll", "1", "--grace", "0",
                        "--max-restarts", "1", "--", PY, "-c", "import time; time.sleep(2)"])
    if rc != 0:
        failures.append(f"[fresh-hb] healthy child should exit 0 (not be restarted), got {rc}")


def test_stale_restart_then_alert(failures, tmp):
    """A child that hangs and never beats → stale → restart up to the cap → alert + exit 75."""
    hb = os.path.join(tmp, "hb3.json")  # never created → age is None → stale
    marker = os.path.join(tmp, "alerted.flag")
    start = time.time()
    rc = watchdog.main(["--heartbeat", hb, "--stale", "1", "--poll", "1", "--grace", "0",
                        "--max-restarts", "1", "--alert", f"touch {marker}",
                        "--", PY, "-c", "import time; time.sleep(60)"])
    if rc != 75:
        failures.append(f"[stale] exhausted restarts should exit 75, got {rc}")
    if not os.path.exists(marker):
        failures.append("[stale] alert command did not run on exhaustion")
    if time.time() - start > 40:
        failures.append("[stale] took too long — children may not be terminating on restart")


def test_crash_surfaces_fast_not_on_poll_cadence(failures, tmp):
    """A child that crashes (non-zero) must be detected on the FAST child-poll, not deferred to
    the slow --poll cadence — so ans-run's ~2s post-spawn early-exit probe can report the crash
    instead of a false 'Started'. Uses --poll 30 to prove the child isn't waited out for 30s."""
    hb = os.path.join(tmp, "hb-crash.json")
    _hb(hb, time.time())  # fresh so staleness never fires — the exit must come from child-poll
    start = time.time()
    rc = watchdog.main(["--heartbeat", hb, "--stale", "999", "--poll", "30", "--grace", "0",
                        "--max-restarts", "2", "--", PY, "-c", "import sys; sys.exit(5)"])
    elapsed = time.time() - start
    if rc != 5:
        failures.append(f"[fast-crash] child crash rc should pass through (no restart), got {rc}")
    if elapsed > 5:
        failures.append(f"[fast-crash] took {elapsed:.0f}s — child-death must surface fast, "
                        "not on the 30s --poll cadence")


def test_ans_run_composes_watchdog_by_default(failures, tmp):
    """Ticket 03: bin/ans-run wraps the detached launch in the watchdog BY DEFAULT, sizing
    --stale off per_ticket_timeout_s; the opt-out (flag or config) returns the bare argv."""
    from agents_never_sleep.launcher import compose_watchdog_argv
    full = ["claude", "-p", "--dangerously-skip-permissions", "do the work"]
    hb = os.path.join(tmp, "state", "heartbeat.json")

    wrapped = compose_watchdog_argv(full, hb, {}, 1800)
    if wrapped[1:3] != ["-m", "agents_never_sleep.watchdog"]:
        failures.append(f"[compose] default should invoke the watchdog module: {wrapped}")
    if "--heartbeat" not in wrapped or hb not in wrapped:
        failures.append(f"[compose] must pass the heartbeat path: {wrapped}")
    # --stale must comfortably exceed per_ticket_timeout_s (which bounds only ONE gate
    # subprocess) — a ticket's whole implement→gate×N→review→consensus span passes with no
    # beat, so a too-small stale false-restarts a healthy run. Lock in the conservative sizing.
    stale = int(wrapped[wrapped.index("--stale") + 1])
    if stale < 1800 * 2:
        failures.append(f"[compose] --stale ({stale}) too small — must cover a multi-gate "
                        "ticket span, not a single per_ticket_timeout_s (1800)")
    if wrapped[-len(full):] != full or wrapped[-len(full) - 1] != "--":
        failures.append(f"[compose] the agent argv must follow a '--' separator, intact: {wrapped}")

    # Opt-out via flag and via config both return the bare argv unchanged.
    if compose_watchdog_argv(full, hb, {}, 1800, disabled=True) != full:
        failures.append("[compose] --no-watchdog (disabled=True) must return the bare argv")
    if compose_watchdog_argv(full, hb, {"enabled": False}, 1800) != full:
        failures.append("[compose] watchdog.enabled=false must return the bare argv")

    # Config overrides flow through (stale/cap/alert).
    tuned = compose_watchdog_argv(full, hb, {"stale_s": 999, "max_restarts": 5,
                                             "alert": "touch /tmp/x"}, 1800)
    if tuned[tuned.index("--stale") + 1] != "999" or \
       tuned[tuned.index("--max-restarts") + 1] != "5" or "--alert" not in tuned:
        failures.append(f"[compose] config overrides (stale/cap/alert) not honored: {tuned}")


def main() -> int:
    failures = []
    tmp = tempfile.mkdtemp(prefix="ue-wd-")
    test_child_exits_clean(failures, tmp)
    test_fresh_heartbeat_no_restart(failures, tmp)
    test_stale_restart_then_alert(failures, tmp)
    test_crash_surfaces_fast_not_on_poll_cadence(failures, tmp)
    test_ans_run_composes_watchdog_by_default(failures, tmp)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — watchdog not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — clean-exit passthrough, fresh-heartbeat no-restart, and "
          "stale→restart→alert→exit-75 all hold (sidecar; claude-run untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
