# Orchestrator session prompt — retired

This file is **retired** (#127). It held the pasted prompt for a person's own
interactive session to drive a whole plan by firing hand-provisioned cloud
routines, back when that setup was a manual step done before a run.

That mechanism is gone. Driving a plan is now **`/plan-run`**, which follows
[`skills/staged-rollout/references/remote-driver.md`](../../skills/staged-rollout/references/remote-driver.md)
directly: it fires each stage itself via `RemoteTrigger`, watches it, and
moves to the next one — nothing to paste in first.

This file is kept only so old links to it keep resolving. Its content is no
longer maintained and should not be pasted anywhere.
