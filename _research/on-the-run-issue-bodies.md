# "on the run" — the seven issue bodies, for review

Drafted 24 Aug 2026. NOTHING HAS BEEN FILED. This file is the approval copy.

Target: `by-carlos/plan-staged-rollout` (PUBLIC) -> board Claude Plugins (#3),
label `enhancement`, Status left at board default.
Structure: issues 1-6 filed as sub-issues of the parent. Only real dependency:
6 blocked-by 4 and 5. Start with #1.

| # | Title | Priority | Size | Effort |
|---|---|---|---|---|
| P | Tracker: "on the run" - cloud-first unattended mode for staged rollouts | P2 | L | unset |
| 1 | on the run: map the routine configuration surface (repository, model, plugins) | P1 | XS | sonnet-low |
| 2 | on the run: verify a routine run can load a skill committed to the cloned repository | P1 | S | sonnet-high |
| 3 | on the run: verify a routine run can perform the full stage git cycle | P1 | S | sonnet-high |
| 4 | on the run: write the stage-runner routine prompt contract | P2 | M | opus-high |
| 5 | on the run: write the orchestrator session prompt contract | P2 | M | opus-high |
| 6 | on the run: prove the full lifecycle end to end on a throwaway repository | P2 | L | opus-high |

---



===============================================================
## PARENT - Tracker: "on the run" - cloud-first unattended mode for staged rollouts
===============================================================

### In plain terms

Running a large build as many small, unattended sessions currently only works if a computer is switched on and has a working Python setup, because the loop that drives each stage runs there. This project, codenamed "on the run", aims to run that same lifecycle from a phone instead, with the computer off the whole time. The core question was whether one unattended stage can automatically trigger the next one on its own. It cannot: the automation that would need to do the triggering only exists on surfaces a person is actively logged into, not inside an unattended run itself. So the link between stages has to be a person (or a person's already-authenticated session) closing the loop, not a fully self-driving chain — which changes the shape of the design from "set it running and walk away" to "a lightweight session that fires each step and checks in between."

### Context

`plan-staged-rollout`'s unattended mode today is `scripts/plan_driver.py`: a loop that re-reads `.plan/LEDGER.md` and `.plan/PLAN.md`, computes the runnable stage set, and launches one fresh `claude -p` session per stage. It requires the maintainer's computer to be on. "On the run" is the cloud-first replacement, driven from a phone via Claude Code cloud routines. Direct, hands-on testing against a live account on 23–24 Aug 2026 established the following:

- **A routine-run session cannot fire another routine.** No tool available inside a run accepts a routine id to fire. An unauthenticated POST to the routine fire endpoint made from inside a run returns HTTP 401 — there are no ambient credentials to do it any other way.
- **A routine-run session cannot durably create a routine either.** Searching its tool index for routine/trigger creation surfaces only a session-local cron tool. That tool's own schema states jobs die with the session — no durable persistence. An end-to-end test (routine A instructed to create routine B) produced no routine B in the trigger registry afterwards.
- **The trap:** the session-local cron tool accepts a `durable: true` flag that has no measurable effect, and a "child" job scheduled through it fires as another turn inside the *same* session, not a new one. In a transcript this looks exactly like successful routine chaining. It is not — the trigger registry is the only reliable check, not the transcript.
- **Root cause:** routine management (create/list/fire) is carried by a meta-connector that is only present on user-credentialed surfaces — the phone app, the desktop app, an authenticated CLI session. The cloud routine-run worker itself does not carry this connector; inside a run, only ordinary connectors are visible.
- Therefore the chaining link between stages must be external to the run: a user-credentialed session (which can itself run in the cloud and be driven from a phone) fires each stage's routine in turn. Routines can be fired manually, so no fixed schedule is required.
- **Plugins do not load in a routine run by default.** Two separate probe runs both reported `plan-staged-rollout` and personal plugin skills unavailable — only the stock skill set was visible.
- A trigger does carry a documented `enabled_plugins` field: top-level, server-validated, typed as a string array (a non-string value is rejected with `invalid value for string field enabled_plugins`). Plausible values (`plan-staged-rollout`, `carlos`, `plan-staged-rollout@by-carlos`) were each accepted with HTTP 200 and stored back as an empty array — validated against something, then silently dropped. The correct identifier format is undocumented and was not guessable from the API.
- Similarly, `extra_marketplaces` is typed as `[{name: <string, required>, source: <object, required>}]`. A bare string for `source` is rejected; an object is accepted but tolerates unknown keys and silently drops the whole entry when it doesn't resolve. The correct shape of `source` was not established.
- **Confound on the plugin probes:** every probe routine created through the API reported "No sources configured" — no repository attached — so those probes tested plugin availability only, never repository-committed skills. The field that attaches a repository was not found anywhere in the API surface; routines created through the web form do carry a repository and clone it at run start.
- **Documented but untested escape hatch:** the routines documentation states a run can use skills committed directly to the cloned repository (e.g. under `.claude/skills/`). Vendoring a stage-runner skill into the target repository on the plan branch would make the design independent of plugin loading entirely, sidestepping the `enabled_plugins`/`extra_marketplaces` unknowns above.
- **Run environment:** a fresh Ubuntu VM per run (~4 vCPU / 16 GB / 30 GB), `gh` pre-installed, GitHub access through a proxy that serves REST but only a pinned set of GraphQL operations — so Projects v2 is unreachable through it, and some `gh` subcommands need REST fallbacks. Repositories are cloned from the default branch; pushes to `claude/`-prefixed branches are unrestricted, other branches are allowed only when unprotected, carrying no other author's commits, and with no other open PR from them.
- **Run visibility is surface-dependent.** An authenticated CLI session can read a run's condensed transcript through the routine API. The phone-side tool family can list triggers, fire them, and list sessions, but has no run-log reader at all. A cloud-first orchestrator must therefore judge stage completion from the pushed `.plan/LEDGER.md`, not from run logs.
- Fire text arrives wrapped as untrusted data — a routine's saved prompt must explicitly opt in to acting on it, or the run treats it as inert context.
- A routine run acts as the account owner's GitHub identity, with no per-action approval during the run.
- Routines draw on a daily run cap per account, and GitHub webhook triggers have per-routine and per-account hourly caps during the research preview.

_Surfaced while researching cloud-mode feasibility — Claude Code session `a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

**Recommended: phased approach.** First, probe the remaining unknowns (exactly how to configure an unattended run's repository/model/plugin access, and whether repository-committed logic actually loads and runs, and whether a run can complete the full git lifecycle — branch, push, pull request, merge — on its own). Second, once those are answered, write the two prompt contracts this design needs: the contract each unattended stage run follows, and the contract the person-driven "fire the next stage and check the ledger" session follows. Third, prove the whole thing end to end on a disposable repository, driven entirely from a phone, with an automated pass/fail check rather than a manual read of the outcome. This order avoids writing contracts against assumptions that later turn out to be wrong, and avoids a "big bang" proof attempt before the individual pieces are known to work.

**Rejected — a fully self-advancing chain of unattended runs.** This was the first design considered and is the one directly disproved by testing: nothing available inside an unattended run can trigger or durably create another one. There is no known workaround short of the platform adding that capability.

**Rejected — keep the existing loop, but run it as a background session instead of a local process.** This still requires a computer to host that background session continuously, which is exactly the requirement this project exists to remove. It would reduce nothing about the core constraint being solved for.

### AI prompt

This is a tracking issue, not a unit of work — do not implement against it directly. It exists to coordinate six sub-issues that together deliver "on the run": three unknowns to probe (routine configuration surface, whether repository-committed skills load in a run, and whether a run can complete a full git branch/PR/merge cycle), two prompt contracts to write (the per-stage unattended run, and the person-driven orchestrating session), and one end-to-end proof of concept on a disposable repository with an automated verification script. Work each sub-issue in its own PR against its own scope. Close this tracking issue only once the end-to-end proof-of-concept run has passed using its automated verification script — not when the sub-issues are merged, since passing the real run is the actual claim being tested.


===============================================================
## 1 - on the run: map the routine configuration surface (repository, model, plugins)
===============================================================

### In plain terms

Running a build automatically in the cloud means telling the automation which
project repository to work in, which model to run it with, and which extra
capabilities it should have loaded. Right now there is no reliable way to set
any of those three things programmatically: the setting is either accepted
without complaint and then quietly ignored, or its correct name and format are
simply unknown. A person can still set all three by hand through the web
interface, but nothing scripted can be trusted to configure a run correctly
today. This blocks any plan to automate the setup step itself, not just the
build the automation eventually runs.

### Context

Measured 23–24 Aug 2026 against a live account, via direct calls to the
routine API (`create`, `update`, `get`, `list`, `run`, `list_runs`,
`get_run_log`), not inferred from documentation:

- `enabled_plugins` is a top-level, server-validated field on a routine,
  typed as a string array. A non-string value is rejected outright with
  `invalid value for string field enabled_plugins`. Plausible plugin
  identifiers (`plan-staged-rollout`, `carlos`, `plan-staged-rollout@by-carlos`)
  are all accepted with HTTP 200, but the field reads back as an empty array
  `[]` every time — validated against something, then silently dropped. The
  correct identifier format was not discoverable from the API surface itself.
- `extra_marketplaces` takes the shape `[{name: <string, required>, source:
  <object, required>}]`. A bare string for `source` is rejected with
  `unexpected token`. A well-formed object for `source` is accepted — and
  tolerates unknown keys — but the entry is silently dropped when it does not
  resolve to a real marketplace. The internal shape `source` expects was not
  established.
- `job_config.ccr.environment_id` is required on `create`; omitting it makes
  the API return HTTP 400 outright, so a routine cannot be created at all
  without first knowing which environment id to reference.
- Every routine created directly through the `create` API in this round of
  testing had its run log report the literal line `No sources configured` —
  no repository attached — regardless of what was sent. A routine created
  through the web form, by contrast, does carry a repository and clones it at
  run start. So the field (or mechanism) the web form uses to attach a
  repository was not found through the API — only the web-form path is known
  to work.

_Surfaced while researching cloud-mode feasibility — Claude Code session
`a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

- **Keep guessing values for `enabled_plugins` and `extra_marketplaces`
  against the API.** Rejected — already tried with several plausible values
  for both and the failure mode (silent accept-and-drop, HTTP 200 either way)
  gives no signal to converge on the right answer. More guessing spends
  effort without a way to tell progress from noise.
- **Create one routine through the web form with a repository, model, and
  plugin set correctly by a person, then read its stored configuration back
  via the `get` API — recommended.** The web form is already known to produce
  a routine with a real repository attached (no `No sources configured` in
  its run log), a model selected, and a plugin enabled. Reading that object
  back reveals the actual repository-attachment field, the model field, and
  the value `enabled_plugins` actually needs, which the API silently rejects
  when guessed. Once known, the orchestrator only ever calls `update` and
  `run` against this one pre-configured routine rather than `create`-ing
  routines from scratch, which sidesteps the unresolved creation-time gaps
  entirely.

### AI prompt

Goal: determine the real field name and value format for repository
attachment, and the actual value `enabled_plugins` needs to stop being
silently dropped, by reading back a routine that was configured correctly
through the web UI.

Precondition (human, one-time, not part of this session's work): a routine is
created through the web form pointing at a throwaway repository, with a
specific model selected and the `plan-staged-rollout` plugin enabled. Do not
attempt to substitute this step with a `create` API call — that is the exact
thing this probe is meant to avoid guessing at, and `create` also requires a
`job_config.ccr.environment_id` that is not yet known to be correct.

Steps:

1. Locate the routine (trigger) created in the precondition and call the
   `get` action (or `list` and filter) to fetch its full stored
   configuration. Dump the complete JSON response.
2. From that JSON, identify and record: the field name and value shape used
   for the attached repository (and whether it names a branch, or defaults to
   the repository's default branch); the field name and value used for the
   selected model; the value `enabled_plugins` actually holds now that it is
   not empty; and the value of `job_config.ccr.environment_id`, since any
   future `create` call needs a valid one.
3. Confirm each finding by reproducing it: issue an `update` call against the
   same routine (or a second throwaway routine, created via the web form to
   sidestep the `environment_id` requirement) using exactly the field
   names/values just discovered — including a value for `enabled_plugins` —
   then call `get` again and confirm the values persisted rather than reading
   back as `[]` or empty. A value that round-trips correctly is proof; a
   value that reads back empty or unchanged is not.
4. Do not touch `scripts/plan_driver.py` or the plugin's own code — this is
   routine-API reconnaissance only, against throwaway or test routines and
   repositories.
5. Close out by recording, directly in this issue, the confirmed field
   name/value pair for repository attachment, model selection, and
   `enabled_plugins`, plus the exact JSON snippet from the `update`/`get`
   round-trip that proves each one stuck.


===============================================================
## 2 - on the run: verify a routine run can load a skill committed to the cloned repository
===============================================================

### In plain terms

Automated cloud runs need custom, project-specific instructions to know how to
carry out a build stage, but the usual way of supplying those instructions —
an installed plugin — is not available inside this kind of run. The
documented workaround is to instead bundle the instructions as a file inside
the project itself, so the run picks them up automatically when it checks out
the code. Nobody has actually tried this yet. If it does not work as
documented, the entire approach to giving these automated runs custom
behaviour needs to be rethought from a different starting point, since the
usual mechanism is confirmed unavailable.

### Context

Measured 23–24 Aug 2026 against a live account:

- Two separate probe routine runs both reported that neither the
  `plan-staged-rollout` plugin's skills nor a personal plugin's skills were
  available inside the routine-run session; only the stock, built-in skill
  set was visible.
- Documentation for routines states a run can load skills committed directly
  to the cloned repository, under `.claude/skills/`, as an alternative to
  plugin-supplied skills. This claim has not been tested.
- Earlier probing of `enabled_plugins` (see the sibling config-surface probe
  issue) turned out to be inconclusive for an unrelated reason: every routine
  created directly through the `create` API in that round had its run log
  report the literal line `No sources configured` — no repository attached at
  all — so those probes tested plugin availability only, never
  repository-committed skills. This probe needs a routine with a real
  repository attached, which is known to work when the routine is created
  through the web form.
- The mechanism under test here is meant to replace, inside a routine run,
  what `scripts/plan_driver.py` does locally: reading `.plan/LEDGER.md` and
  `.plan/PLAN.md` to run one stage at a time. A skill committed under
  `.claude/skills/` is the candidate way to give a routine run the same
  stage-running instructions without depending on `enabled_plugins`.

_Surfaced while researching cloud-mode feasibility — Claude Code session
`a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

- **Keep pursuing `enabled_plugins` until its value format is confirmed, and
  depend on plugin loading as the delivery mechanism.** Rejected as the
  primary path — even once the field's format is known (issue 1), it still
  depends on trusting a field that has already been observed to silently
  drop values it doesn't recognise, re-checked on every run. A
  repository-committed skill is visible directly in the checked-out code,
  travels with the plan branch, and doesn't depend on any account-level
  configuration at all.
- **Vendor a minimal probe skill into a throwaway repository and fire a
  routine against it — recommended.** Directly tests the documented escape
  hatch with a repository now known to attach correctly, and produces a
  provable pass/fail result rather than another round of inconclusive
  probing.

### AI prompt

Goal: prove or disprove that a skill file committed to a repository's
`.claude/skills/` directory is both visible to and actually invoked by a
routine run that clones that repository, independent of any plugin
configuration.

Steps:

1. In a throwaway public repository, add a minimal skill at
   `.claude/skills/probe-skill/SKILL.md` with YAML frontmatter containing
   `name: probe-skill` and a `description` that states plainly when to use
   it, e.g. "Use when asked to run the on-the-run probe check." The skill
   body's only instruction should be: write the literal marker string
   `ON_THE_RUN_PROBE_OK` to a file named `probe-result.txt` in the repository
   root, then commit and push that file.
2. Attach this repository to a routine — reuse the routine configured in the
   config-surface probe issue once repository attachment is confirmed
   working there, or create a fresh one through the web form.
3. Fire the routine with prompt text that explicitly asks it to run the
   on-the-run probe check (matching the skill's stated trigger phrase), and
   that explicitly opts in to acting on the fire payload — fire text
   otherwise arrives as inert, untrusted context and will not be acted on.
4. Verify from outside the run, not by trusting its transcript: after the run
   completes, check the repository directly (via an authenticated session or
   the web UI) for a commit adding `probe-result.txt` with the exact marker
   string. That commit is the proof the skill was both found and executed.
   Its absence, or a result file with different content, means the skill was
   not picked up, or the run improvised an equivalent action without it —
   either way, not a pass.
5. Where possible, also confirm from the run's condensed transcript (readable
   only from an authenticated CLI session, per prior findings — not from
   phone-side tooling) that the skill was actually listed as available and
   named as invoked, as a secondary check alongside the committed file.
6. Do not touch `enabled_plugins` — this probe must succeed using only a
   committed skill, independent of any plugin configuration, to prove the
   documented escape hatch stands on its own.
7. Close out by recording, directly in this issue, the exact repository path
   used, whether the skill was listed as available, and whether the marker
   commit appeared — this is what issue 4's stage-runner contract will rely
   on if it passes.


===============================================================
## 3 - on the run: verify a routine run can perform the full stage git cycle
===============================================================

### In plain terms

For an automated cloud run to actually complete a build stage on its own, it
has to do more than edit files: it needs to work on the right branch rather
than the one it starts on, push its changes, open a pull request, and merge
that pull request, all without a person clicking anything. The rules that
govern what this kind of run is allowed to do suggest this should work, but
nobody has actually run the full sequence and checked the result. There is
also a real chance that part of the sequence depends on functionality this
kind of run cannot fully reach, because its access to the code-hosting
service is more limited than a normal session's. Until the whole sequence is
proven, there is no reliable claim that a stage can actually land on its own.

### Context

Measured 23–24 Aug 2026 against a live account:

- A routine run starts from a fresh cloud virtual machine with the
  repository cloned from its **default branch** — never from the plan branch
  (`plan-<slug>`) that `scripts/plan_driver.py` operates against locally.
  Work can be pushed freely to `claude/`-prefixed branches, which are always
  accepted; other branches are accepted too, but only when they are
  unprotected, carry no commits from any other author, and have no other
  open pull request already against them.
- `gh` is pre-installed in the cloud environment, but GitHub access goes
  through a proxy that serves the full REST API, while only a fixed, pinned
  set of GraphQL operations is reachable. Some `gh` subcommands rely on
  GraphQL operations outside that pinned set and are expected to need a
  REST-based fallback (`gh api ...`) instead — which specific subcommands
  need it has not been catalogued.
- Separately, the design this probe supports assumes a stage session pushes
  its branch immediately after its first commit, before doing anything
  else — because a run that dies before pushing is indistinguishable, from
  the ledger (`.plan/LEDGER.md`) an external orchestrator reads, from a stage
  that never started at all.

_Surfaced while researching cloud-mode feasibility — Claude Code session
`a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

- **Defer this check to when the stage-runner prompt contract is written, and
  treat any git failure as something discovered then.** Rejected — that
  defers discovery of a possible blocking failure until much later in the
  sequence, including past the point where an end-to-end proof of concept is
  attempted, which is the most expensive place to find out the mechanism
  doesn't work.
- **Run a small, scripted probe now that performs the exact sequence in
  isolation and checks the result from outside the run — recommended.**
  Cheap, isolated, and answers the question before anything else depends on
  it.

### AI prompt

Goal: confirm, with a real fired routine run, that the full sequence —
switch to a non-default branch, create and push a stage branch, open a pull
request, and merge it into the non-default branch — completes successfully
and unattended, and catalogue which `gh` subcommands needed a REST fallback.

Setup:

1. Create a throwaway public repository with two branches: `main` (the
   default) and a second, unprotected branch named `plan-probe`, standing in
   for the `plan-<slug>` plan branch PSR uses. `plan-probe` should contain at
   least one plain text file to edit.
2. Attach this repository to a probe routine (reuse a routine from the
   config-surface or repository-skills probes once repository attachment is
   confirmed working, or create one through the web form).

Fire the routine with prompt text that instructs it, precisely, to:

1. Check out (fetch and switch to) `plan-probe` — not the default branch the
   clone starts on.
2. Create a new branch off `plan-probe`, e.g. `stage-probe-1`.
3. Make one trivial, verifiable edit — append a distinctive marker line
   (include a timestamp) to the existing text file — and commit it.
4. Push `stage-probe-1` immediately after that first commit, before doing
   anything else, to test the push-early assumption.
5. Open a pull request from `stage-probe-1` into `plan-probe` using
   `gh pr create`.
6. Merge that pull request into `plan-probe` using `gh pr merge` — not into
   `main`.
7. If any `gh` subcommand in this sequence fails because of the GraphQL proxy
   restriction, fall back to the equivalent `gh api` REST call and note, in
   the run's own output, exactly which subcommand needed the fallback and
   what replaced it.

Verify from outside the run, not by trusting its own transcript — using a
separate authenticated session or the web UI against the throwaway
repository:

1. `plan-probe`'s history shows the merge commit, and the marker line with
   its timestamp is present in the file on `plan-probe`.
2. The pull request shows a merged state, not merely opened.
3. No commits from any author other than the routine's identity landed on
   `plan-probe`, and `main` was not touched at all.

Close out by recording, directly in this issue: whether the full sequence
completed unattended with no blocking approval prompt; the exact list of
`gh` subcommands, if any, that needed a REST fallback and what the
replacement call was; and whether the push-early step behaved as expected
(the branch existed remotely immediately after the first commit, before the
PR was opened).

Do not touch PSR's real plan branch, stage protocol, or driver script — this
is confined to the throwaway repository. Do not merge into the throwaway
repository's default branch under any circumstance; only the non-default
integration branch, mirroring the real plan-branch model.


===============================================================
## 4 - on the run: write the stage-runner routine prompt contract
===============================================================

### In plain terms

When one step of a large, multi-step build runs unattended in a hosted cloud
session instead of on someone's own computer, the instructions that session
follows have to be extremely narrow. It must do only the one step it was
assigned, record that it finished in the shared progress log, and stop — never
decide on its own to skip ahead, retry, fold its work into the project's main
line, or take on anything nobody assigned it. That instruction text does not
exist yet, so nothing currently enforces those limits. Written too loosely, an
unattended step could merge into the project's main line, run a step that was
meant to wait for a person, or leave no trace of what it did — and because
nobody is watching a hosted run in real time, that would only be discovered
after the fact.

### Context

Part of "on the run": making a staged, multi-session build (a PSR plan)
runnable end to end from a phone, with the computer off, by firing one Claude
Code routine per stage. Each fired routine runs as its own disposable session
with no interactive prompts and no permission-mode picker — its saved prompt
is the only guardrail it has.

Measured facts this contract has to encode:

- A routine's fire payload — which stage to run — arrives wrapped as
  untrusted data. The saved prompt must explicitly opt in to acting on it, or
  the run treats it as inert context and does nothing.
- The run's repository is cloned fresh from the default branch, not the plan
  branch the build is actually working on — the prompt has to check out the
  plan branch itself before doing anything else.
- The only way anything outside the run can tell whether a stage finished, and
  how, is the row it writes to `.plan/LEDGER.md` — a companion probe
  established that the phone-side tooling used to fire routines cannot read a
  fired run's transcript back at all; only an already-authenticated CLI
  session can.
- The run acts as the account owner's GitHub identity, with no per-action
  approval during the run.
- A stage marked `gate: human` is never supposed to be fired unattended in the
  first place — this prompt is the last line of defence if one is fired by
  mistake anyway.

_Surfaced while researching cloud-mode feasibility — Claude Code session
`a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

**Recommended: one generic stage-runner routine, parameterised per fire.**
The same saved prompt is reused for every stage and told which one to run
through the fire payload, rather than writing a separate routine per stage.
It's one place to fix a bug or add a constraint instead of N near-duplicates
drifting apart. Caveat: if a routine turns out to allow only one model choice
for everything it runs, a plan with stages at different effort levels might
still need one routine per weight class rather than truly one for all — the
config-surface probe (sub-issue 1) settles whether that's actually required.

**Rejected: one hard-coded routine per stage.** Duplicates the same
constraints N times, drifts as soon as one copy is fixed and the others
aren't, and still needs the same unresolved configuration answers from
sub-issue 1 to set each one up. Doesn't scale with plan size.

**Rejected: folding retry or sequencing logic into the stage-runner prompt.**
Deciding what runs next, retrying a failed stage, or watching for a stall
belongs entirely to the orchestrator side of this project (sub-issue 5).
Duplicating any of it here is exactly the failure mode this contract has to
avoid — the stage-runner prompt should know about nothing but the single
stage it was fired for.

### AI prompt

**Goal:** write the saved prompt a stage-runner routine runs, and commit it
as a reviewable, versioned file in this repository — for example under
`examples/on-the-run/stage-runner-prompt.md` (the exact path is a judgement
call for whoever picks this up, but it must be a committed file, not text
that only ever lives pasted into the routine's web-form field, or the
contract has no record anyone can review or diff).

**Binding constraints the prompt must encode** (each is a measured fact, not
an assumption — do not soften or generalise any of these):

- Explicitly opt in to treating the fire payload — which stage to run — as an
  actionable instruction. Left implicit, it is inert.
- Check out the plan branch before doing anything else; the clone the run
  starts with is the default branch, not the plan branch.
- Push the stage's own branch early, before the bulk of the stage's work. A
  run that dies before pushing is indistinguishable, from outside, from one
  that never started at all.
- Treat writing the ledger row as the only completion signal. Nothing else
  the run does is visible to whatever fired it.
- Never merge into the repository's default branch, under any circumstances.
  The plan-to-main merge is permanently a manual, human-performed step and
  this contract must not create an exception to it.
- If the fired stage is marked `gate: human`, refuse the work and record that
  refusal rather than attempting it anyway.
- Assume no permission prompt and no per-action approval is available during
  the run — the saved prompt is the only control on what the run is allowed
  to touch.

**What must NOT be added.** This contract is deliberately minimal; adding
logic is the failure mode, not an improvement:

- No retry loop, no attempt counter, no "try the next stage anyway" behaviour.
  If the stage doesn't reach a settled state, the run stops; a person decides
  what happens next.
- No decision-making about which stage should run, or about overall plan
  sequencing. The prompt should only ever know about the single stage it was
  fired for — sequencing is the orchestrator's job (sub-issue 5).
- No notification logic of its own. The design already treats the
  tool-permission prompt raised by creating or firing a routine as the
  per-stage notification; don't build a second channel here.
- No new state, flags, or side files beyond the existing ledger row. Anything
  else is state the orchestrator has no way to see and therefore cannot act
  on.

**Do not touch:** the format of `.plan/LEDGER.md` or `.plan/PLAN.md`. The
prompt must read that format as it already exists; if something the contract
needs is missing from it — a per-stage routine/model column, say — that's a
gap for its own issue, not something to improvise around here.

**How to verify:** this contract cannot be meaningfully verified alone.
Verification happens in the git-cycle probe (sub-issue 3) and the end-to-end
proof of concept (sub-issue 6). This issue is done when the prompt text is
written, committed, and a self-check confirms every binding constraint above
is explicitly named in it.


===============================================================
## 5 - on the run: write the orchestrator session prompt contract
===============================================================

### In plain terms

Running a large, multi-step build unattended from a phone needs something
that plays conductor: it reads the shared progress record, starts the next
piece of work, waits to see whether that work finished, and repeats — over
and over until the whole build is done. That conductor has to stay almost
deliberately simple: it must never guess at a fix when something looks wrong,
never quietly retry on its own, and must always hand a step that specifically
needs a human back to that human rather than attempting it. None of that
exists yet in a form that can run this way, so today the only way to drive
the whole sequence is for a person to carry out every step themselves, by
hand, on their own computer.

### Context

Part of "on the run": making a staged, multi-session build (a PSR plan)
runnable end to end from a phone, with the computer off. The orchestrator is
the user-launched, interactive session that drives the plan by firing one
Claude Code routine per stage and watching for it to settle — it is not
itself unattended; a person keeps it open (from the phone), and it is
deliberately dumb by design.

Measured facts and design decisions this contract has to encode:

- The tooling available from the phone can list routines, fire them, and list
  sessions, but has no way to read a fired run's transcript at all. Reading a
  transcript needs an already-authenticated CLI session, which defeats the
  point of driving this from a phone. The orchestrator must therefore judge
  whether a stage finished — and how — strictly from `.plan/LEDGER.md` after
  it's pushed, never from run logs.
- The ledger is the only state the orchestrator holds. It's re-read fresh
  every round rather than kept in memory, because the orchestrator is a
  single long-running interactive session and context is the resource that
  runs out first.
- No automatic retry. If a stage dies without the ledger reaching a settled
  state, the orchestrator reports what it knows and waits for a person to
  inspect the run and continue manually — this mirrors how the existing local
  driver (`scripts/plan_driver.py`) already behaves when a session
  disappears.
- A stage marked `gate: human` is never fired; the orchestrator recognises it
  from the plan index and hands it back to the maintainer instead.
- The plan-to-main merge always stays manual — the orchestrator stops before
  it, regardless of how the rest of the run went.
- Creating or firing a routine already raises a tool-permission request in
  the orchestrator's own session, which doubles as the per-stage notification
  channel. No separate notification mechanism is needed — but approving that
  permission permanently would silently remove this channel, which is worth
  flagging to whoever runs the orchestrator.

_Surfaced while researching cloud-mode feasibility — Claude Code session
`a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

**Recommended: a minimal read → fire → poll → repeat loop, serial only for
the first pass.** Each round: read the ledger, compute the next runnable
stage, fire its routine, poll the ledger until it settles, repeat. Parallel
firing is easier in the cloud than locally — each fire is its own VM, so the
worktree collision that limits local parallelism doesn't apply — but it's
explicitly out of scope for this contract; add it later once the serial path
is proven.

**Rejected: giving the orchestrator its own retry logic**, mirroring the
local driver's retry-then-block behaviour. Rejected because "no automatic
retry" is the actual design decision here, not an oversight to fix — an
unsettled stage is a signal for a person to look, and quietly retrying would
hide exactly the failures a phone-driven, unattended-adjacent design most
needs surfaced.

**Rejected: letting the orchestrator read run transcripts when a richer
session happens to have that tool available.** This would work from a desktop
CLI session but silently stop working the moment the same contract is run
from the phone-side tooling, which has no transcript reader at all. The
contract has to work identically on both, so the ledger has to be the only
source of truth, unconditionally.

### AI prompt

**Goal:** write the orchestrator's operating instructions — the prompt or
checklist a person runs at the start of their own interactive session (from
the phone or otherwise) to drive a plan — and commit it as a reviewable,
versioned file in this repository, for example under
`examples/on-the-run/orchestrator-prompt.md` (exact path is a judgement call,
but it must be committed, not text that only lives in a chat transcript).
This is distinct from the stage-runner routine's saved prompt (sub-issue 4):
that one runs inside a fired routine; this one runs the interactive session
that does the firing.

**Binding constraints the contract must encode** (each is a measured fact or
an explicit design decision — do not soften or generalise any of these):

- Judge stage completion strictly from `.plan/LEDGER.md` once it's pushed,
  never from a fired routine's run log or transcript — the phone-side tooling
  cannot read one back at all.
- Hold no state beyond what's re-read from the ledger each round; don't carry
  a remembered picture of plan progress forward in the conversation.
- Never fire a stage marked `gate: human`; recognise it from the plan index
  and hand it back to the maintainer instead.
- Stop before the plan-to-main merge, unconditionally — that step is always
  performed by the maintainer by hand.
- On any stage that doesn't reach a settled ledger state, report what's known
  and wait for a person; never retry automatically and never guess at a fix.
- Rely on the tool-permission prompt raised by creating or firing a routine as
  the per-stage notification; note the caveat that approving it permanently
  removes this signal.

**What must NOT be added.** This contract is deliberately minimal; adding
logic is the failure mode, not an improvement:

- No retry counter, no backoff, no "fire it again and see" step.
- No fallback to reading run transcripts or logs, even when the session
  happens to have that capability — the contract must work identically from
  the phone, where that capability doesn't exist.
- No stage-level work of its own. The orchestrator never edits code and never
  touches the target repository's contents beyond reading the ledger; all
  actual work happens inside the fired stage routines.
- No parallel firing in this pass — serial only. Don't add concurrency just
  because nothing in the cloud technically blocks it; it's explicitly
  deferred scope.
- No merge behaviour of any kind — not the plan branch's stage PRs (that
  happens inside each stage run) and not the final plan-to-main PR (that's
  the maintainer, by hand).

**Do not touch:** the format of `.plan/LEDGER.md` or `.plan/PLAN.md`, and
don't change `scripts/plan_driver.py` — this contract is a separate,
cloud-first path alongside the existing local driver, not a replacement for
it.

**How to verify:** this contract cannot be meaningfully verified alone.
Verification happens in the end-to-end proof of concept (sub-issue 6). This
issue is done when the prompt/checklist is written, committed, and a
self-check confirms every binding constraint above is explicitly named in it.


===============================================================
## 6 - on the run: prove the full lifecycle end to end on a throwaway repository
===============================================================

### In plain terms

Once the two instruction sets behind this project exist — one for the
individual step, one for the conductor that sequences them — the only real
test is running an actual, small build start to finish using nothing but a
phone, with the computer that would normally do this switched off, and seeing
whether it produces working, merged results without a person carrying out any
individual step by hand. The test has to include one step that only a human
can approve, and a final step where a person merges the finished work
themselves, because those two things are supposed to stay manual no matter
what. If the whole thing can't actually be driven from a phone alone, the
core premise — that this kind of build can run without a computer — doesn't
hold, regardless of how well each instruction set works in isolation.

### Context

Part of "on the run": making a staged, multi-session build (a PSR plan)
runnable end to end from a phone, with the computer off, by firing one Claude
Code routine per stage from an interactive orchestrator session.

Proof-of-concept scope, as agreed: a throwaway repository, driven start to
finish from a phone. Two automatic stages that make real edits and open real
pull requests; one stage that requires human input (a `gate: human` stage the
orchestrator correctly refuses to fire); a closeout whose plan-to-main merge
the maintainer performs by hand. The plan ships with a verification script
that the final stage runs, so "did it work" is a command to run rather than a
transcript to read. Stages use real models at real effort levels — the point
is to measure what a run would actually cost and ship, not to exercise a
stub.

This build is deliberately not run as a PSR plan against this repository —
using this plugin's own mechanism to build its cloud mode would be circular
and would confuse the record, so a disposable repository is used instead.

_Surfaced while researching cloud-mode feasibility — Claude Code session
`a79da687-5ed7-4401-bfb0-53d6419dd587`, 24 Aug 2026 NZST._

### Options

**Recommended: run this only after the earlier sub-issues land** — the
config-surface mapping, the repository-committed-skill check, the git-cycle
probe, and both prompt contracts. Running the full end-to-end attempt before
those are answered would rediscover the same unknowns one at a time inside a
live, harder-to-debug run instead of via targeted, isolated probes; a failure
partway through wouldn't say which of several independent unknowns caused it.

**Rejected: skipping straight to this proof of concept.** Faster to start,
but any failure becomes much more expensive to diagnose, since it could stem
from the routine configuration, the skill-loading mechanism, the git cycle,
or either prompt contract, with no isolated result to point at the cause.

**Rejected: treating this issue as the point where "on the run" becomes a
documented, supported plugin mode.** This issue only proves the lifecycle
works once, end to end. Whether to document and ship it as a supported mode
is a separate decision for later, using this run's findings as evidence.

### AI prompt

**Goal:** run a full plan lifecycle end to end in a disposable repository,
driven entirely from a phone with the computer off, and confirm the result
with a verification script.

**Constraints:**

- Use a throwaway repository, not this one.
- The plan needs exactly: two automatic stages that make real edits and open
  real pull requests; one stage marked `gate: human` that the orchestrator
  must correctly refuse to fire unattended; and a closeout stage whose
  plan-to-main merge the maintainer performs by hand, not the orchestrator or
  any stage routine.
- The `gate: human` stage must exercise the **whole** path, not just the
  refusal: the orchestrator refuses and reports, the maintainer runs that
  stage interactively, and the orchestrator then resumes and carries on to
  the next stage. A run that only proves the refusal has proved half of it.
- Every stage runs at a real model and effort level — no stubbed-out
  low-cost placeholder stages.
- Ship a verification script that the final stage runs, so pass/fail is
  produced by a command, not judged by reading transcripts. At minimum it
  asserts: every stage branch exists and is merged into the plan branch; each
  stage's pull request is closed as merged; `.plan/LEDGER.md` shows every row
  settled as done or skipped with no row left at doing; the working edits each
  stage claimed are actually present on the plan branch; and nothing was
  merged into the default branch.
- Drive the entire run from a phone, start to finish, with no reliance on the
  computer being powered on at any point.

**What NOT to do:**

- Don't fold findings from this run directly back into the stage-runner or
  orchestrator prompt contracts in place — record what's found and route it
  back to the owning sub-issue instead, since each contract has its own
  issue.
- Don't use this issue to decide whether "on the run" becomes a documented,
  supported plugin mode. That packaging decision is explicitly out of scope
  here; this issue only proves the lifecycle once.

**How to verify:** the verification script's pass result, plus confirmation
that the whole run — every stage fire, the human-input step, and the final
manual merge — was driven from a phone with the computer off throughout.
