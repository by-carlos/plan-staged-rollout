## In plain terms

When a monitored site is down, the status page only says "down". People reading it cannot tell whether it went down a minute ago or last night. This adds the time of the last successful check next to every down site, so readers can judge how long the outage has lasted.

## Context

Support asked for this after two incidents in which customers could not tell a brief blip from a long outage. The checker already stores the time of every check, so no new data is needed. Only the page that renders the table of sites has to read it.

## Rollout notes

No flag and no migration. The new column appears on the next page build. Tell support once it ships so they can point customers at it.

## Acceptance Criteria

1. Every site shown as down also shows the time of its last successful check
2. A site that has never had a successful check shows "never" in that place
3. Sites that are up look exactly as they do today

## AI prompt

Repository `example-org/status-page`, base branch `main`. In the page renderer, add the last successful check time to every down row, using the timestamps the checker already stores. Show "never" when there is none. Verify with a unit test for a down site with history and one without, then render the page against the sample config and confirm up sites are unchanged.
