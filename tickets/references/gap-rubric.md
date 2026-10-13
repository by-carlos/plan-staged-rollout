# Gap-review rubric

The gap reviewer reads a **draft** ticket before the user approves it. It
finds what is missing or vague and turns each gap into a short question for
the author. Pushback should be cheap: a few pointed questions, not a
rewrite.

## How it runs

- **Model:** a Sonnet-tier subagent, never a Haiku-tier one (a lighter
  model is likely to skip a rule without saying so). The main session never
  reviews its own draft.
- **Input:** the draft Ticket (see `adapter-contract.md`), the resolved
  template, this rubric and, when there was one, the **source material** the
  ask was drafted from (the thread, document or existing ticket, as text).
  Every check except `source-fidelity` judges the draft alone, so the review
  still sees what a later reader will see; the source exists so that what
  the drafter dropped, smoothed over or invented can be caught. When the
  source was split, the other tickets' titles come with it: what one of
  them covers was moved, not dropped.
- **Output:** one JSON list, worst first:

  ```json
  [{"check": "measurable-ac", "severity": "blocker | gap | nit",
    "where": "Acceptance Criteria, bullet 2",
    "finding": "\"get it approved\" cannot be checked",
    "question": "Who approves it, and where does the approval show?"}]
  ```

  A `guarded-field` item also carries `"field": "<template field key>"`.
  `scripts/ticket_core.py review-filter` validates the list, resets each
  finding to the severity this table gives its check (template
  `extra_checks` are gaps), keeps every blocker, cuts gaps to
  `max_questions` and returns the cut ones, and replaces a guarded-field
  question with a neutral one built from the field's `ask_when`, so the
  reviewer's wording can never steer the answer.

- **At most `review.max_questions` questions** (default 5) reach the user.
  Blockers come first, then the gaps marked **Always asked**, which are never
  cut, then the other gaps. Nits go into the draft directly, and the
  skill reports them, but never asks about them.
- **Blockers** must be answered or explicitly waived by the user before the
  approval gate. The waiver is recorded in the draft notes, never in the
  ticket body.

## Checks

Ordered by how often each gap appeared in real ticket samples. The most
common gaps come first.

| # | Check | Severity | Fails when |
|---|---|---|---|
| 1 | `structure` | blocker | A required section is missing or empty, or the sections are out of template order. |
| 2 | `measurable-ac` | blocker | An acceptance criterion cannot be checked by someone other than the author ("investigate", "improve", "get approved", "works well"), or there are none. Each one must name an observable result. |
| 3 | `stands-alone` | blocker | The body is only a link or a one-line ask: a reader must open something else to learn what is wanted. A linked thread or document must be summarized in the body. |
| 4 | `why` | gap | Context does not say why the work exists, or why now if it is urgent. |
| 5 | `named-references` | gap | A bare URL, a bare ticket key, or a bare repo or document name. Every reference is a link whose text is a human-readable name, with the identifier after it. |
| 6 | `title` | gap | The title does not explain the work: it is a channel name, "PR review", "please help", or carries a date or an urgency word. Applies the template's `[title]` rules. Urgency goes to priority or a due date. |
| 7 | `action` | gap | The ticket does not say what is different when it is closed. A ticket that only produces a finding must name who will use it. |
| 8 | `scope` | gap | Out of scope is missing and the ask has an obvious neighbour that someone could assume is included. |
| 9 | `size` | gap | The estimate is above the template's `split_above` value, or there are many unrelated acceptance criteria. Propose a split, or a time-boxed spike when sizing is impossible. |
| 10 | `dependencies` | gap | Work that clearly depends on another team, system, approval or ticket does not name it, or names an open blocker without saying so. |
| 11 | `estimate-sanity` | nit | The proposed estimate disagrees with the template's matrix for the answers given, or the value is the scale's minimum on a ticket with no acceptance criteria (a defaulted look). |
| 12 | `duplicates` | gap | The adapter's `duplicates` search returned a likely match. The user decides; the reviewer only raises it. |
| 13 | `guarded-field` | blocker | The draft mentions data a guarded field covers (its `ask_when`), and the field has no recorded answer. The reviewer **asks**. It never infers a guarded value, and it never suggests one. |
| 14 | `operational-ask` | gap | A request to run or change something in a live system is missing any item of the template's `intake.operational_checklist`: target, environment, expected effect, rollback or confirmation. |
| 15 | `ai-prompt` | gap | There is an AI prompt section but it is not self-contained, or it lacks what `body.ai_prompt.requires` lists (`effort`: an opening `Proposed model/effort:` line; `repo`, `base_branch`), or it has no verification step. When there is **no** AI prompt but an AI agent could do the work or a clear part of it, the reviewer asks whether the ticket should carry one. |
| 16 | `plain-words` | nit | A `no_identifiers` section contains keys, ids, paths or codenames, or a term no outsider would know is left undefined. |
| 17 | `source-fidelity` | gap | Only when source material was given. The draft drops a requirement, constraint or open question the source states; softens something the source states firmly; or claims something the source does not say. Separately, a term in the source that nothing defines (a code, a record or system name, an unnamed "standard") is questioned whether or not the draft kept it: ask what it is and who owns it, never ask to restore it, because the source can be wrong. **Always asked**, never cut by `max_questions`. |
| 18 | `unsourced-decision` | gap | The draft states a choice as already settled (a mechanism, a policy, a target value, who signs off) without naming the standard, decision record or person it rests on. Raise it especially where the choice carries security, reliability, data or compliance risk. Ask whether it was decided and where; when it was not, the honest ticket is often the decision itself. When the template lists `references`, a draft touching what one covers is asked, by the reference's name, whether it was checked against it, and a draft that contradicts one of its points says which. **Always asked**, never cut by `max_questions`. |
| 19 | `plausibility` | gap | A claim with no evidence or stated confidence; a term that does not belong to the technology it is attached to (an event, table or setting name the product does not have); or an ask that does not fit the system (a production database backed up to a phone). Ask what it is and where it comes from, never declare it wrong: the reviewer's knowledge can be stale, and internal names exist that it cannot know. **Always asked**, never cut by `max_questions`. |

Template rules from `[review].extra_checks` run after these with severity
`gap`. Tickets matching `[review].skip_when` (for example, machine-created
review tickets) skip the review entirely, and the skill says so.

## What the reviewer never does

- It never rewrites the draft. It points and asks; the drafter changes the
  text.
- It never reviews the floor test. That ran before the draft existed.
- It never decides priority or the estimate. It only checks them against
  the template.
- It never sees or proposes tracker ids. Field values come from the
  template, not from the review.

## Fixtures

The skill is exercised by hand on at least three synthetic drafts:

- a vague one-line ask (should hit `stands-alone`, `measurable-ac`, `title`)
- an oversized story (should hit `size` and propose a split)
- an ask that may touch regulated data (should hit `guarded-field` and ask,
  never set the value)

Real tickets that informed the ranking are kept privately and are not
fixtures.
