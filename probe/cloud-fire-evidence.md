# Cloud Fire Session Evidence

## Model
`claude-haiku-4-5`

(From system prompt: "This session is configured for the model `claude-haiku-4-5`. The model actually serving a turn can differ from that and can change mid-session (the runtime falls back, or the model is switched), so do not state which model you are from this line alone.")

## CLAUDE_EFFORT Environment Variable

Command: `echo "$CLAUDE_EFFORT"`
Output: (empty)

## CLAUDE_CODE_EFFORT_LEVEL Environment Variable

Command: `echo "$CLAUDE_CODE_EFFORT_LEVEL"`
Output: (empty)

## Starting Branch

Before the stage branch was created, the container started on:
- Branch: `plan-cloud-fire-probe-s0-wcssqj`

Note: The branch already existed when the session started, checked out in the main clone (which violated the worktree protocol). During preflight step 0.4, this drift was corrected by checking out the plan branch (`plan-cloud-fire-probe`) in the clone and creating a sibling worktree for the stage branch.

## Plugin Slash Commands Available

No

The session instructions state: "This is a cloud container, so the plan-staged-rollout plugin is not loaded and its slash commands do not exist here."
