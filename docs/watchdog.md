# ANS Watchdog

> **30-second version.** The watchdog is a **sidecar** that catches the one failure the Stop-hook cannot
> see: a *hang* (the run is alive but making no progress — e.g. a run wedged by a sustained 529/overload
> wave that freezes the heartbeat). It runs the agent as a child, polls its heartbeat file, and when the
> heartbeat goes stale it kills and **restarts the run resumable**; on exhausted restarts it fires an
> alert and exits `75`. **`ans-run` now wraps every detached launch in it by default** (opt out with
> `--no-watchdog`), so an overnight run can recover from an overload freeze instead of sitting dead until
> morning. It also **reaps the run's own leaked child processes** (the agent's MCP servers) by parent-chain
> lineage, so a long run doesn't creep toward OOM. It is composed *around* a command, never a rewrite of
> any shared wrapper. See [recovery](recovery.md), [launcher](launcher.md), [security](security.md),
> [glossary](glossary.md).

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

You rarely invoke this by hand: `bin/ans-run` composes the watchdog around every detached launch **by
default** and passes sane flags (heartbeat path, `--stale`, `--max-restarts`), holding the working-tree
lock across restarts. Opt out with `ans-run --no-watchdog`, or tune it under `launcher.watchdog`
(`enabled`, `stale_s`, `max_restarts`, `poll_s`, `grace_s`, `alert`) in the config.

## Sizing `--stale` correctly (load-bearing)

`--stale` **must exceed the real worst-case gap between heartbeats**, or the watchdog false-restarts a
healthy run — which then re-stales, exhausts the cap, and exits `75`, killing a run that was fine. In the
agent-driven loop the heartbeat is only beaten at `next`/`complete` boundaries, so a single ticket's
**whole** span passes with no beat: implement → up to `per_ticket_fix_iterations` gate rounds → architect/
security review → consensus → `complete`. `per_ticket_timeout_s` (default 1800s) bounds only *one gate
subprocess*, not that whole span — so when `ans-run` composes the watchdog it sizes `--stale` off
`per_ticket_timeout_s × (per_ticket_fix_iterations + 1) + a review/consensus margin`, not the bare budget.
(The `watchdog.py` CLI default remains a conservative 2400s for a hand-composed call; raise it, or set
`launcher.watchdog.stale_s`, when your tickets carry heavy review/consensus gates.) Sizing it too low is
the dangerous direction; too high only delays catching a genuine hang.

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

## Reaping leaked child processes (`reap.py`)

A killed or crashed coding-agent leaves its own children alive — the MCP servers it spawned (context7,
project MCP, the `npm`/`sh` wrappers). Their parent (an editor/`vscode-server`) keeps them, so they don't
look orphaned (`ppid != 1`) and nobody reaps them; across a long or repeatedly-restarted run they pile up
(one real incident: ~13 GB, swap full → OOM risk for the services on the box). So the watchdog reaps the
run's **own** child tree:

- **Rooted at the agent's pid, walked by parent-chain lineage** (`reap.descendants`), never a name match.
  A `pkill -f claude` would match the reaping command *and* kill other users' / other projects' runs — a
  foot-gun ANS never uses. Rooting the walk at the agent pid means it can only ever reach that agent's own
  subtree: not the watchdog (its parent), not a sibling run, not another user (a cross-user signal fails
  with `EPERM` anyway). The reaper also refuses `pid <= 1`.
- **When:** on a restart (the tree is captured *before* the kill, because a dying process's children
  reparent and the lineage is erased), on a graceful `SIGTERM`/`SIGINT` of the watchdog, and via a rolling
  per-poll snapshot so a *spontaneously*-crashed agent's orphaned MCP servers are still reaped by pid.
- **Honest limit:** a force-*killed* (`SIGKILL`) watchdog cannot run its own handler, so it can't self-reap
  — that residual leak is **reduced, not eliminated**.

## Per-run capability restriction (optional)

An agent preset may declare a `capabilities` list (e.g. `--strict-mcp-config --mcp-config <file>`) so a run
loads only the MCP servers / tools it needs — a smaller memory footprint and attack surface. Absent = the
full set (today's behaviour). This is per-**run**, not per-ticket (ANS launches once for the whole backlog).

## Boundary

The watchdog governs *liveness* and *resource hygiene* of an execution run — it restarts a hung run and
reaps that run's own leaked children; it does not judge code, choose models, or verify output. Detecting
and restarting a hang is execution-resilience, squarely within ANS's scope. See the [glossary](glossary.md)
ecosystem table.

## Limitations

The watchdog detects a stale **heartbeat**, not semantic wedging that still beats the heartbeat — a process
that loops while regularly updating its heartbeat would not be restarted. The `--stale` threshold is a
trade-off: too low false-restarts healthy long tickets, too high delays catching a real hang. Restart count
is bounded (`--max-restarts`); a persistently hanging environment ends at exit `75` rather than restarting
forever. Reaping is best-effort within its stated bounds: a `SIGKILL`'d watchdog can't self-reap, and only
the run's *own* lineage is ever signalled.

---

*Verified against `agents_never_sleep/` (v1.0.0): `watchdog.py` (child-process supervision, restart on stale
heartbeat, `--max-restarts` default 3, exit 75, `--alert`, tree reaping on restart/signal/crash-snapshot),
`reap.py` (parent-chain `descendants`/`reap_pids`, refuses pid ≤ 1), `launcher.py` (default watchdog compose
+ `--stale` sizing + `capabilities`), `heartbeat.py` (`next`/`complete` beats), `driver.py` (resume-safe
restart).*
