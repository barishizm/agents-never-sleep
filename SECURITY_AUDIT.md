# Security & Privacy Audit — agents-never-sleep (ANS)

**Date:** 2026-07-08
**Scope:** the whole repository at branch `claude/security-privacy-audit-ns9em9` — the stdlib harness
(`agents_never_sleep/`), the launcher (`bin/ans-run` + `agents_never_sleep/launcher.py`), the Claude
bash hooks (`hooks/`), the cross-platform enforcement core (`enforcement.py` / `enforce.py`), the
platform adapters, the Paperclip/Vault integrations, and the supporting docs.
**Method:** manual source review of every module, plus targeted dynamic checks (the deny-hook
patterns, the redactor, and the enforcement env-gating were exercised with crafted inputs; findings
tagged **[verified]** were reproduced, not merely reasoned about).

---

## Executive summary

ANS is, for a tool in this class, **unusually security-conscious**, and that should be said up front
so the findings below are read in proportion. The design already gets the hard things right:

- Every subprocess is invoked with an **argv list, never a shell**, except two deliberate
  `shell=True` sites that are gated by TOFU trust (`launcher.run_config_checks`) or are
  operator-authored (`watchdog --alert`). No `eval`/`exec`/`os.system`/`pickle`/`yaml.load`.
- **No untrusted data reaches a shell or a git argument.** Ticket bodies/titles/ids never flow into
  commit messages, branch names, or command arguments; the one ticket-authored value that reaches a
  copy-pasteable command (`declared_agent`) is validated against a strict slug regex
  (`tickets.py:16,48`).
- **TOFU config-trust** is done correctly: SHA-256 of the exact bytes that are parsed (no TOCTOU
  second read), stored **outside** the repo, `0600`, and the store-path env override is neutered
  unless an explicit test flag is set (`trust.py:28-39`).
- Reversibility is careful: WIP is backed into a durable `refs/ans-backup/*` before any destructive
  reset, and a git step that can't be verified fails to the safe side (HALT), not a silent proceed
  (`vcs.py`, `driver.py:_resume_is_safe`).
- Process reaping is by **parent-chain lineage rooted at the agent pid, never by name**, with a
  `pid <= 1` guard (`reap.py`) — avoiding the classic `pkill -f` self-kill / cross-tenant foot-gun.
- The working-tree lock opens with `O_NOFOLLOW`; state writes are atomic (temp + fsync + replace);
  the raw agent log is created `0600`; resolved secrets are registered with a redaction layer.
- The docs are refreshingly honest about limits ("primary protection is your execution environment",
  "deny-hooks are a backstop", live-verified only on Claude Code).

The findings below are therefore mostly about **residual gaps in defense-in-depth layers** and
**claims that are slightly stronger than the code delivers** — not gaping holes. The two that matter
most are a set of **trivial, standard-form bypasses of the "never irreversible" deny-hook** (H1) and
a **launch-flag combination that silently disables the entire enforcement layer** (M1). Neither is a
remote-code-execution or credential-dump primitive on its own; both defeat an *advertised, testable*
guarantee, which `SECURITY.md` explicitly invites as a vulnerability report.

### Findings at a glance

| ID | Severity | Title |
|----|----------|-------|
| H1 | **High** | Irreversible-action deny-hook is bypassed by standard command forms (`git -C … push --force`, `+refspec`, `rm -r -f /`, `find / -delete`) |
| M1 | Medium | `ans-run --no-watchdog` (and `--fg`) launch a detached run **without** `CLAUDE_UNATTENDED=1`, so every enforcement hook is inert |
| M2 | Medium | Secret redactor misses common credential shapes (Stripe, Google, SendGrid, generic `NAME_PASSWORD=…`), leaking them into gate artifacts and the run report |
| M3 | Medium | The irreversible denylist is duplicated (bash vs Python) and can drift; the "single source of truth" module does **not** cover the only live-verified platform |
| L1 | Low | Harness state dir + JSON records are created world-readable (umask default) while the log/notes are deliberately `0600`/`0700` |
| L2 | Low | Resolved Vault/creds-file secrets are written into the shared process env and inherited by the gate (test) subprocess |
| L3 | Low | Root-launch re-exec honors `launcher.target_user` from the **untrusted** config before the TOFU gate; only uid 0 is refused |
| L4 | Low | Run-log is opened without `O_NOFOLLOW` (the lock file correctly uses it) |
| L5 | Low | Vault/Paperclip token endpoints default to plaintext `http://`; a misconfigured non-loopback URL transmits the bearer token in the clear |

---

## HIGH

### H1 — The "never irreversible" deny-hook is bypassed by standard command forms **[verified]**

**Where:** `hooks/deny_irreversible.sh:45-56` (Claude Code — the only *live-verified* platform) and
the mirrored `agents_never_sleep/enforcement.py:33-46` (`_IRREVERSIBLE`, used by every other
platform).

**Risk.** `SECURITY.md` and `docs/security.md` state as a guarantee to test against that force-push,
remote branch/tag delete, destructive SQL, and disk-destructive commands "are denied by the hooks",
and the README FAQ says deny-hooks "block irreversible/outward actions at the source (force-push,
remote branch deletes, destructive SQL, secret deletion, disk wipes)." The matcher is a **denylist of
narrow literal patterns**, and the exact operations it names slip through in their most ordinary
alternate spellings. Verified against both the bash hook and the Python core:

| Command | Verdict |
|---|---|
| `git push --force origin main` | DENIED |
| `git -C . push --force origin main` | **ALLOWED** |
| `git push origin +main` (force via `+` refspec) | **ALLOWED** |
| `git -c protocol.version=2 push --force` | **ALLOWED** |
| `rm -rf /` | DENIED |
| `rm -r -f /` (separated flags) | **ALLOWED** |
| `rm --recursive --force /` | **ALLOWED** |
| `find / -delete` | **ALLOWED** |

The root cause is that `git\s+push` requires `git` immediately followed by `push`, so any global git
option (`-C`, `-c`, `--git-dir`, `--work-tree`) between them defeats the match; force-push via a `+`
refspec isn't modeled at all; and the `rm` pattern assumes a single combined `-rf`/`-fr` token.
Because the agent is exactly the party a rogue ticket, a poisoned repo file, or an injected
council/tool result can steer, "the agent would never phrase it that way" is not a safe assumption —
these are the *first* forms a scripted or prompt-injected agent reaches for.

**Fair context.** This is a defense-in-depth backstop: the docs correctly say the sandbox/least-priv
user is the primary control, and `docs/security.md:91-95` already admits "a novel destructive command
outside the patterns could slip through." The gap here is sharper than that hedge, though — these are
not novel commands, they are the *enumerated* ones in standard forms — and it is invited explicitly
as a vuln by `SECURITY.md`.

**Fix.**
1. Normalize before matching: strip leading `git` global options (`-C <path>`, `-c k=v`,
   `--git-dir=…`, `--work-tree=…`) so `git … push …` is recognized regardless of interposed options.
2. Add the missing force/delete forms: a `+` in a push refspec (`git push \S+ .*\+`), long-form and
   separated `rm` flags (`rm` with any combination of `-r`/`-R`/`--recursive` **and**
   `-f`/`--force` targeting `/`, `~`, `$HOME`), and a generic recursive-delete escape hatch
   (`find … -delete`, `find … -exec rm`).
3. Re-frame the doc/`SECURITY.md` language from "blocks force-push / disk wipes" to "blocks the
   enumerated patterns as a backstop; the sandbox is the boundary" so the promise matches the
   mechanism. A denylist over a Turing-complete shell can never be complete (`bash -c`, base64
   decode, aliases, env indirection all bypass it) — the honest posture is "backstop + sandbox",
   and the code should not out-claim that.

---

## MEDIUM

### M1 — `--no-watchdog` / `--fg` launch a detached run with enforcement completely inert **[verified]**

**Where:** `agents_never_sleep/launcher.py:823-824` (builds `child_env` with no
`CLAUDE_UNATTENDED`), `:872` / `:899-905` (detached spawn), `:848-856` (`--fg` exec); the **only**
place the launcher stack sets the switch is inside the watchdog at
`agents_never_sleep/watchdog.py:98`.

**Risk.** Every enforcement hook — `deny_ask.sh`, `deny_irreversible.sh`, `stop_guard.sh`, and the
cross-platform `enforce.py` — is inert unless `CLAUDE_UNATTENDED=1` (or `UE_UNATTENDED=1`) is in the
agent's environment. The default background launch is wrapped in the watchdog, which sets it, so the
happy path is safe. But `ans-run --no-watchdog … "prompt"` spawns the **bare agent** with
`env=child_env`, which never contains `CLAUDE_UNATTENDED`. Result: a detached, unattended run in which
never-ASK, deny-irreversible, and never-stop are **all silently off** — unless the operator happened
to export the variable by hand. The safety layer is thus coupled to an unrelated *resilience* feature:
opting out of automatic restart also opts out of all structural guarantees. `--fg` has the same gap,
though a human is nominally attached there.

The docs are inconsistent about whose job it is: `docs/tutorials/claude-code.md:110` tells the
operator to set it in the cron wrapper, while `docs/tutorials/unattended-scheduling.md:182` says the
watchdog sets it — so an operator who trusts "ans-run handles unattended launches" and uses
`--no-watchdog` gets an unprotected run with no error and no blind-spot note.

**Fix.** In `launcher.main()`, set `child_env["CLAUDE_UNATTENDED"] = "1"` for **every detached
(non-`--fg`) spawn**, independent of the watchdog, so the enforcement switch is owned by the launcher
and never coupled to `--no-watchdog`. (Keep the watchdog setting it too — belt and suspenders.) For
`--fg`, either set it as well or emit a loud one-line notice that interactive permission-gating is now
the only guard. Optionally, have `ans-run` refuse a detached launch when it cannot confirm the switch
will be set.

### M2 — Secret redactor misses common credential shapes **[verified]**

**Where:** `agents_never_sleep/redact.py:53-86` (`_PATTERNS`, shape-anchored) and `:46-49`
(`_SECRET_ENV_VARS`, the literal-registry allowlist).

**Risk.** Redaction is one of the four advertised guarantees ("never leak a secret into a log or
report"). It has two halves: a shape matcher (backstop) and a literal-value registry (precise). The
registry only harvests six env names (`PAPERCLIP_TOKEN`, `VAULT_TOKEN`, `TOKONOMIX_*`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), so any *other* credential is protected by shape matching
alone — and the shape matcher misses very common formats. Verified leaks (the string survives
`redact()` unscrubbed and would land in the saved gate artifact `.unattended/artifacts/…` and the run
report):

| Secret | Result |
|---|---|
| Stripe secret key `sk_live_…` | **LEAKED** (the `sk-` pattern requires a hyphen; Stripe uses `_`) |
| Google API key `AIza…` | **LEAKED** |
| SendGrid key `SG.…` | **LEAKED** |
| Generic `MYSQL_PWD=…` / `DB_PASSWORD=…` | **LEAKED** (only URL- and header-embedded passwords are caught) |
| Twilio `SK…` | **LEAKED** |
| OpenAI `sk-…`, Slack `xox…`, AWS `AKIA…`, `Bearer`/`Authorization`, `scheme://user:pass@host` | redacted ✓ |

The biggest single write surface is the saved raw gate/test output (`redact.py` docstring names it
"the biggest risk"): a project whose test suite echoes a Stripe/Google/DB credential on failure will
have it persisted and surfaced.

**Fair context.** `docs/secrets.md:84-89` states redaction is "a backstop, not a proof that a secret
in any conceivable shape is caught", and the literal registry is the real guarantee. This is a
coverage improvement to a defense-in-depth layer, not a broken promise — hence Medium, not High.

**Fix.** Add shape patterns for the common providers above (`\bsk_live_`, `\brk_live_`, `\bAIza[0-9A-Za-z_\-]{35}\b`,
`\bSG\.[\w\-]{16,}\.[\w\-]{16,}`, Twilio `\bSK[0-9a-fA-F]{32}\b`), and add a **generic
keyword-anchored assignment** rule that redacts the *value* after `*(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*` while
preserving the key name (the same `\g<p>…` technique already used for `authorization:`), which
sidesteps the "don't shred our own prose" concern because only the assigned value is replaced.
Broaden `_SECRET_ENV_VARS` (or make it configurable) so more resolved values enter the precise
registry.

### M3 — Duplicated irreversible denylist that can drift; the canonical copy doesn't protect the live-verified platform

**Where:** `hooks/deny_irreversible.sh:42-56` vs `agents_never_sleep/enforcement.py:33-46`, with the
module's own docstring (`enforcement.py:12-16`) acknowledging: *"the Claude adapter … keeps its own
copy of the irreversible patterns. The canonical copy now lives HERE … converging deny_irreversible.sh
onto this module is a documented follow-up."*

**Risk.** The security-critical denylist exists in two hand-maintained copies. Claude Code — the only
platform ANS claims as *live-verified* (`README.md`, `capabilities.py`) — runs the **bash** copy;
`enforcement.py` (the "single source of truth") serves the other, *not*-live-verified platforms. So a
new "never do X" pattern added to the canonical Python module silently fails to protect the one
platform the project stakes its verification claim on, and vice-versa. H1 already shows the two are in
lockstep *today* only because both are equally incomplete — but nothing enforces that, and the review
comment treats convergence as optional ("avoid refactoring proven security code without need"). A
security denylist maintained in two places will drift.

**Fix.** Make the Claude bash hook call the same decision core as everyone else (it can shell to
`python3 -m agents_never_sleep.enforce claude pre_tool`, exactly as `hooks/enforce.sh` already does
for other platforms — the plumbing exists), or generate both from one data file. Failing that, add an
acceptance test that asserts the bash hook and `enforcement.decide` return identical verdicts over a
shared corpus (including the H1 cases), so drift is caught mechanically.

---

## LOW

### L1 — Harness state directory and its JSON records are world-readable

**Where:** `state.py:99` (`OutcomeStore.__init__` — `os.makedirs(state_dir, exist_ok=True)`, no
mode), `run.py:55-56`, `heartbeat.py:22`, `ledger.py:66`, and the various `.unattended/state`
writers — none set a restrictive mode, in contrast to `launcher.open_log` which deliberately chmods
the **log** dir to `0700` (`launcher.py:611-615`) and `scratchpad.append_note` which opens notes
`0600` (`scratchpad.py:52`).

**Risk.** Under the common umask (`022`) the `.unattended/` tree and its files (`pending.json`,
`ledger.json`, `run-progress.json`, per-ticket outcome `*.json`) are world-readable. Those records
carry ticket context and the agent's free-text `attempted`/`exact_blocker` fields, which are scrubbed
only as *defense-in-depth* (`state.py:121-125` — "a credential pasted into the agent's free-text
fields") using the same imperfect matcher as M2. The project already decided this content is
sensitive enough to redact and to `0600` the log; leaving the state records world-readable on a shared
host (multi-user server, shared CI runner) is inconsistent with that stance.

**Fix.** Create `.unattended/` (and `state/`, `artifacts/`) with mode `0700`, mirroring `open_log`'s
treatment of the log dir; `chmod` on creation so a pre-existing looser dir is tightened.

### L2 — Resolved secrets are materialized into the shared process env and inherited by the gate

**Where:** `run.py:162` (`os.environ["TOKONOMIX_API_KEY"] = r.value` after a `vault:`/`env:`
resolve), `run.py:117` (`os.environ.setdefault("TOKONOMIX_API_KEY", _key)` from
`~/.tokonomix/credentials.json`); consumed by `gates.py:54` (`env = dict(os.environ)`), which runs the
project's **gate/test command** with that environment.

**Risk.** The whole point of a `vault:` token-ref is to keep the key out of the environment. But
`run.py` resolves it and writes it back into `os.environ`, from where it is inherited by the gate
subprocess — i.e. the project's own (possibly third-party) test suite now sees a credential it
otherwise wouldn't, and so does any child the harness spawns. This widens the exposure of a secret the
token-ref design took pains to keep narrow. Low because the value is redaction-registered and the gate
is broadly trusted, but it is a real "least privilege" regression.

**Fix.** Pass resolved secrets only to the specific consumer that needs them (e.g. the council/agent
env) rather than the global `os.environ`, or explicitly scrub `TOKONOMIX_API_KEY` (and other resolved
refs) from the env handed to `GateRunner`. At minimum, document that the gate command inherits any
resolved token-ref.

### L3 — Root-launch re-exec trusts `target_user` from the untrusted config, pre-TOFU

**Where:** `launcher.py:779-786` (root-guard reads `launcher.target_user` via a direct `json.load`
of the repo config and calls `reexec_as_target_user`) — this runs **before** `check_trust`
(`launcher.py:793`); `reexec_as_target_user`/`_user_is_root` (`:167-203`) only refuse uid 0.

**Risk.** When `ans-run` is started as root, it reads `target_user` from the *not-yet-trusted* repo
config and does `sudo -H -u <target_user> …`. Dropping privilege is the safe direction and the value
goes to `sudo` as an argv element (no shell), so this is not code-exec. But `_user_is_root` blocks
only uid 0 — a malicious repo could name any existing non-root account, including one with effective
root (a member of the `docker` group, a sudoer, or an account whose `~/.config/agents-never-sleep/trusted.json`
already blesses this repo), steering *which* identity the run assumes before any trust check. Requires
the launcher to be started as root (already discouraged) and a suitable account to exist, so Low.

**Fix.** Require the config to be TOFU-trusted (or take the target from a CLI `--target-user`, not the
repo config) before honoring a re-exec target; and/or validate `target_user` against an operator
allowlist. Keep the "must not be root" refusal, but recognize that non-root ≠ unprivileged.

### L4 — Run-log opened without `O_NOFOLLOW`

**Where:** `launcher.py:894` (`os.open(log_path, O_WRONLY|O_CREAT|O_APPEND, 0o600)`) and the
fresh-session variant `launcher.py:670`; contrast `acquire_lock` (`launcher.py:582`) which correctly
uses `O_NOFOLLOW`.

**Risk.** The log holds the agent's raw, **unredacted** stream (the very reason it's `0600`). Opening
it through a pre-planted symlink in the log dir would append that unredacted stream to an
attacker-chosen file, or clobber a file the runner can write. Low likelihood — ANS creates the log
dir `0700` and the filename is timestamped — but the lock file already sets the precedent that these
opens should be symlink-safe.

**Fix.** Add `os.O_NOFOLLOW` to both log opens (and consider it for the trust-store/state temp files
that live in potentially shared trees).

### L5 — Token endpoints default to plaintext HTTP

**Where:** `keysource.py:27` (`_DEFAULT_VAULT_ADDR = "http://127.0.0.1:8200"`),
`sources/paperclip.py:66-72` / `config.py:91` (`base_url` default `http://localhost:3100`,
`Authorization: Bearer` sent over it).

**Risk.** The defaults are loopback, so cleartext is fine as shipped. But nothing warns if
`VAULT_ADDR` / `integrations.paperclip.base_url` is set to a **non-loopback** `http://` endpoint — in
which case the Vault token / secret-id / AppRole material and the Paperclip bearer token cross the
network in the clear.

**Fix.** Emit a blind-spot/warning when a resolved token is about to be sent to a non-loopback,
non-`https` endpoint; document that remote Vault/Paperclip must be `https`.

---

## Checked and OK (audit trail)

To scope the findings, these were examined and found sound:

- **Command construction** — all git/gate/probe calls use argv lists; the two `shell=True` sites
  (`launcher.run_config_checks`, `watchdog --alert`) are TOFU-trusted / operator-authored and
  documented. No `eval`/`exec`/`os.system`/`pickle`/`yaml.load` anywhere.
- **Injection via ticket/Paperclip content** — ticket ids are sanitized before use as filenames
  (`state.py:102`, `scratchpad.py:32`; `/`→`_` neutralizes traversal on POSIX); ids/bodies never
  reach git refs, commit messages, or argv; `declared_agent` is slug-validated (`tickets.py:16,48`);
  frontmatter is parsed by hand (no PyYAML load).
- **TOFU trust** — hash-of-parsed-bytes (no TOCTOU), store outside the repo, `0600`, env-override
  gated behind `ANS_TEST_MODE` (`trust.py`). Legacy-config and custom-agent paths correctly require
  `allow_custom_agent` + re-trust, and path-bearing `argv0` is refused (`agent_clis.is_allowlisted`).
- **Reversibility** — WIP anchored to `refs/ans-backup/*` before any `reset --hard`/`clean`; protected
  dirs excluded from snapshot and clean; unverifiable git lineage fails to HALT, not proceed
  (`vcs.py`, `driver.py:_resume_is_safe`, `_enter_run_branch`).
- **Process reaping** — lineage-only, rooted at the agent pid, `pid<=1` guarded, EPERM-shielded across
  users; never a name match (`reap.py`).
- **Atomicity** — outcome store, ledger, heartbeat, trust store, config, pending, run-branch all use
  temp+fsync+`os.replace`.
- **Vault error hygiene** — transport errors are sanitized to method/path/code; tokens/secret-ids
  never appear in exception messages (`keysource.py:58-62`); `--version` probe output is discarded so
  a chatty CLI can't leak a resolved ref (`launcher.py:456-459`).
- **Never-ASK / never-stop** — structurally denied/blocked with anti-infinite-loop caps; fail-open on
  malformed payloads so enforcement can never wedge an unrelated tool call (by design).

---

## Priority

1. **H1** — close the standard-form deny-hook bypasses and align the doc/`SECURITY.md` claims with a
   backstop-not-boundary framing.
2. **M1** — set `CLAUDE_UNATTENDED=1` for all detached launches so `--no-watchdog` can't silently
   void enforcement.
3. **M2 / M3** — broaden redaction coverage (or lean harder on the literal registry) and converge the
   two denylists behind one core with a drift test.
4. **L1–L5** — tighten state-dir permissions, stop materializing secrets into the gate env, gate the
   root re-exec target on trust, add `O_NOFOLLOW` to log opens, and warn on plaintext token endpoints.

*No credential material, real or fixture, was found committed anywhere in the repository.*
