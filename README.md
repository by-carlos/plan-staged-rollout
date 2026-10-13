# Plan-Staged Rollout

![Plan-Staged Rollout](docs/hero.jpg)

**Run big projects as many small sessions — not one huge one.**

A Claude Code plugin that breaks a large build into *stages*, executes each
stage in its own fresh session, tracks progress in an evidence-based ledger,
and keeps every decision in exactly one place so the plan never drifts.

```
/plan-staged-rollout:plan-stages <idea>  →  design + decompose into .plan/ (once)
/plan-staged-rollout:stage-run 3         →  execute one stage in a fresh, cheap session (repeat)
/plan-staged-rollout:plan-run            →  drive every remaining stage on the cloud instead (repeat)
/plan-staged-rollout:plan-close          →  final PR, cleanup, done
```

Each is also model-invocable in natural language once installed — e.g. "run
stage 3 of the plan" — the slash form above is the explicit fallback.

And once a rollout is in progress, you don't have to remember any of it: a
`SessionStart` hook detects the `.plan/` directory and tells a fresh session
which stage is next and at what weight — resuming becomes "open a session and
say yes". In repos without a `.plan/`, the hook stays silent (see
[Session-start nudge](docs/staged-rollout.md#session-start-nudge) below).

## Documentation

- [Install and update](docs/install.md)
- [How a staged rollout works](docs/staged-rollout.md)
- [Driving a plan from the cloud](docs/ON-THE-RUN.md)
- [Reference](docs/reference.md)
- [Tickets](docs/tickets.md)
- [Why staged rollouts](docs/why.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Author

Built by **Carlos Eng** —
[GitHub](https://github.com/by-carlos) ·
[LinkedIn](https://www.linkedin.com/in/carlos-eng/)

## License

[FSL-1.1-ALv2](LICENSE) © Carlos Eng — free for any use except building a
competing commercial product, and each release becomes Apache-2.0 two years
after it is made available. Versions released before this change remain MIT.
