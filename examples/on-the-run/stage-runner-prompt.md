# Stage-runner routine prompt — retired

This file is **retired** (#127). It held the pasted prompt for a
hand-provisioned cloud routine that ran one plan stage, back when a person set
up one routine per model before a run.

That mechanism is gone. A stage's contract now lives in **`.plan/RUNNER.md`**,
scaffolded into every plan from
[`skills/staged-rollout/references/templates/RUNNER.md`](../../skills/staged-rollout/references/templates/RUNNER.md).
`/plan-run` fires each stage itself with that file as the instruction, through
`RemoteTrigger` — see
[`skills/staged-rollout/references/remote-driver.md`](../../skills/staged-rollout/references/remote-driver.md)
for the mechanism.

This file is kept only so old links to it keep resolving. Its content is no
longer maintained and should not be pasted anywhere.
