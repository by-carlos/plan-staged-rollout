# Examples

Worked examples of the artifacts this plugin produces. The templates in
[`skills/staged-rollout/references/templates/`](../skills/staged-rollout/references/templates/)
show the *shape* of a scaffold; these show what good **filled-in** content
looks like, so you can judge your own `.plan/` without having to run
`/plan-stages` on a real project first.

## [`uptime-page/`](uptime-page/) — a scaffolded `.plan/`, captured mid-flight

A complete `.plan/` for a toy project — a tiny Python tool that checks a list
of URLs and publishes a static HTML status page — frozen at a realistic
mid-rollout moment:

| Stage | State shown |
|---|---|
| S0 Checker core | `done` — real acceptance output pasted as evidence, plus an as-built note and a gotcha |
| S1 CLI runner | `doing` — stopped mid-stage: completed steps ticked, handoff note in the ledger |
| S2 Status page | `todo` — untouched, exactly as scaffolded |
| SF Plan review | `todo` — the standing final review every plan gets |

### What to notice

The discipline the [plugin README](../README.md) describes, in practice:

- **Ledger rows stay one line.** The status table in
  [`LEDGER.md`](uptime-page/.plan/LEDGER.md) is a 4-line glance; every detail —
  evidence, gotchas, the handoff — lives in the per-stage notes blocks below
  it. The table is re-read by *every* future session, so its size taxes all of
  them; the notes blocks are read only by the stages that depend on them.
- **`done` means evidence, not assertion.** S0's notes block contains the
  actual terminal output of its acceptance checks, pasted — not a claim that
  they passed — followed by the as-built summary and the one gotcha the next
  stages need to know.
- **`doing` is a normal, resumable state.** S1's stage file
  ([`stage-1-cli.md`](uptime-page/.plan/stage-1-cli.md)) has its completed
  steps ticked, and its ledger notes say exactly what is left and where to
  resume. A fresh session picks up from the first unticked box.
- **Flags live only in the PLAN.md stage index.** No stage file restates its
  `depends` / `mode` / `exec` / `model` / `effort` / `gate` — a copy is what drifts.
  The [`PLAN.md`](uptime-page/.plan/PLAN.md) index is the single authoritative
  home the tooling reads.
- **Decisions live only in Frozen decisions.** Stage files and ledger notes
  *point at* `PLAN.md` (see S1's handoff referencing S0's no-raise contract);
  nothing restates a choice.
- **Defaults stay cheap.** Every stage here is `direct` / `inline`, and only
  the keystone (S0) recommends the top-tier model. Escalate a flag only where
  a stage genuinely warrants it.

### Two honest caveats

- At three implementation stages, this toy sits *below* the ~four-session
  floor where the scaffold pays off — it is sized for readability, not as a
  sizing recommendation. See "When NOT to use it" in the skill.
- The example is inert where it lives: the plugin's SessionStart hook only
  reacts to a `.plan/` at the repo **root**, so this nested copy never nudges
  your sessions.

## [`on-the-run/`](on-the-run/) — running a plan from cloud sessions

The committed contract behind
[`docs/ON-THE-RUN.md`](../docs/ON-THE-RUN.md), the quickstart for driving a
plan from your phone by creating one cloud session per stage instead of
running each stage on your own machine. These files are the reviewable
source; the quickstart is where to start if you just want to run one.

> **A cloud session cannot reach anything on your computer or your local
> network** — no local files, no LAN, no secret that lives only on your
> machine, no locally-installed toolchain. Anything a stage needs has to
> already be in the repository or otherwise reachable from the cloud. See
> [`docs/ON-THE-RUN.md`](../docs/ON-THE-RUN.md#what-a-cloud-session-cannot-reach)
> for the full statement, including what this narrows GitHub access down to.

- **[`stage-runner-prompt.md`](on-the-run/stage-runner-prompt.md)** — what a
  fresh cloud session follows to pick and run exactly one stage: check out
  the plan branch, work out which stage is next from the ledger itself,
  follow `.plan/PLAN.md`'s protocol, and stop. Unlike the earlier
  routine-based design, there is no separate session deciding which stage to
  fire — each cloud session works that out on its own.
- **[`orchestrator-prompt.md`](on-the-run/orchestrator-prompt.md)** — the
  checklist for the person driving the loop: what to type into each new
  cloud session, how to read the plan branch to see what happened, when a
  stage needs you instead of a cloud session, and what stays yours by hand
  (the plan-to-`main` merge, in every case).
- **[`poc/`](on-the-run/poc/)** — where the inputs for the next end-to-end
  proof of concept will live, once one is written for this design.

**Status: not yet proven for this transport.** An earlier design — a
pre-provisioned cloud *routine* per model, fired by a persistent chat session
pasted with a different orchestrator prompt — was proven end to end once
([#110](https://github.com/by-carlos/plan-staged-rollout/issues/110)): four
stages on a disposable repository, phone-driven with the computer off, ending
in a verified closeout. That proof does not carry over to the design
documented here; it proved the routine-based mechanism, not cloud sessions
created directly. Nothing on this page claims otherwise, and the two files
above will only lose that caveat once a new proof-of-concept run against
`poc/` passes.
