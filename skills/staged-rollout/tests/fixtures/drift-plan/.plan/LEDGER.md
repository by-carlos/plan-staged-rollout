# Fixture: a proof of concept that is drifting — build ledger

## Status

| Stage | Status | Verified | Date | Result |
|---|---|---|---|---|
| S0 Prototype stream reader | done | yes | 2026-10-20 | Reader streams 1 partition |
| S1 Measure throughput | done | yes | 2026-10-21 | 3x batch throughput; drops under load |
| S2 Retry on dropped connections | doing | — | — | — |
| S3 Back-pressure for slow consumers | todo | — | — | — |
| S4 Write the decision record | todo | — | — | — |
| SF Plan review | todo | — | — | — |

## Notes

### S0 Prototype stream reader
Reader streams one partition end to end.

### S1 Measure throughput
3x the batch throughput; connections drop under sustained load.

### S2 Retry on dropped connections
Added by S1 — connections drop under load, so the measurement cannot finish — referee: grows

### S3 Back-pressure for slow consumers
Added by S2 — a slow consumer stalls the reader during retries — referee: grows

### S4 Write the decision record
_(empty)_

### SF Plan review
_(empty)_
