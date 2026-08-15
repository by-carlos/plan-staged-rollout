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
  `depends` / `mode` / `exec` / `model` / `effort` — a copy is what drifts.
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
