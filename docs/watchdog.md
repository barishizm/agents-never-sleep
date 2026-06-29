# ANS Watchdog

> **30-second version.** The watchdog is an opt-in **sidecar** that catches the one failure the Stop-hook
> cannot see: a *hang* (the run is alive but making no progress). It runs the unattended command as a
> child, polls its heartbeat file, and when the heartbeat goes stale it kills and **restarts the run
> resumable**; on exhausted restarts it fires an alert and exits `75`. It is composed *around* a command,
> never a rewrite of any shared wrapper. See [recovery](recovery.md), [launcher](launcher.md), [glossary](glossary.md).

## The gap it fills

ANS already prevents a premature *stop*: the Stop-hook blocks the agent from ending its turn while the
run-incomplete sentinel exists. But "no progress" is not "a stop". A subprocess can wedge, a network call
can hang forever, a model call can stall — and the run sits there, alive, beating no heartbeat, doing
nothing. The Stop-hook is blind to that. The watchdog (`watchdog.py`) is the answer: a separate process
whose only job is to notice the parent has gone quiet and restart it.

## How it works

```
python3 -m agents_never_sleep.watchdog \
  --heartbeat <repo>/.unattended/state/heartbeat.json \
  --stale 2400 --max-restarts 3 \
  --alert '<command to fire on exhausted restarts>' \
  -- <the unattended command...>
```

- It runs the unattended command as a **child** and polls the child's `heartbeat.json`.
- The heartbeat is beaten at `next`/`complete` boundaries (`heartbeat.py`).
- If the heartbeat goes **stale** past `--stale` seconds, the watchdog kills the child and **restarts it**.
  Because ANS state is durable, the restart resumes exactly where the run was (the in-flight ticket's
  partial edits are reverted to its snapshot; nothing is lost or double-counted — see [recovery](recovery.md)).
- After `--max-restarts` (default 3) exhausted restarts, it runs the optional `--alert` command (e.g. a
  Paperclip issue creator) and **exits `75`**.

## Sizing `--stale` correctly (load-bearing)

The default `--stale` is **2400 seconds**, and the reason matters: in the agent-driven loop the heartbeat
is only beaten at `next`/`complete` boundaries, so a single ticket can legitimately take up to the
per-ticket budget (default 1800s) to implement, plus gate time. **`--stale` must exceed that worst-case
single-ticket work time**, or the watchdog will false-restart a healthy run mid-ticket. 2400s is sized for
the 1800s budget with headroom.

> Read the heartbeat correctly: heartbeat *age climbing during a ticket is normal* — the agent is
> implementing. A genuine stall is high heartbeat age **and** no new commit **and** no file edits. The
> watchdog encodes exactly this via the stale threshold.

## Why a sidecar, not a wrapper rewrite

`claude-run` (and any equivalent shared launcher) is production infrastructure that other crons depend on.
The watchdog is **not** a modification of it. You opt in by **composing** the watchdog *around* the
unattended command — wrap the call (see `WATCHDOG.md`). This keeps the resilience feature additive and
reversible: turning the watchdog off is removing one wrapper, not un-editing a shared tool.

## Exit `75` and alerting

`75` is the watchdog's "exhausted" signal — restarts ran out and the run could not be made healthy. The
`--alert` command lets an operator be told immediately (the InterIP convention is to open a Paperclip issue
in the infra project). The alert is best-effort: a failed alert does not change the exit code.

## Boundary

The watchdog governs *liveness* of an execution run — it restarts a hung run; it does not judge code,
choose models, or verify output. Detecting and restarting a hang is execution-resilience, squarely within
ANS's scope. See the [glossary](glossary.md) ecosystem table.

## Limitations

The watchdog detects a stale **heartbeat**, not semantic wedging that still beats the heartbeat — a process
that loops while regularly updating its heartbeat would not be restarted. The `--stale` threshold is a
trade-off: too low false-restarts healthy long tickets, too high delays catching a real hang. Restart count
is bounded (`--max-restarts`); a persistently hanging environment ends at exit `75` rather than restarting
forever.

---

*Verified against `agents_never_sleep/` (v1.0.0): `watchdog.py` (`--stale` default 2400, `--max-restarts`
default 3, exit 75, `--alert`, child-process supervision), `heartbeat.py` (`next`/`complete` beats),
`driver.py` (resume-safe restart), `WATCHDOG.md`.*
