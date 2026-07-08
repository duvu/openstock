# Closed-loop AI repair note

This note clarifies the intended target state of the file-based observability work.

The target is not only to write logs for human review. The target is a closed-loop workflow:

```text
system runs and interacts with users
  -> logs activities, warnings, errors, traces, commands, and deploy events
  -> packages logs into an AI-readable evidence bundle
  -> AI coding agent reads the bundle and proposes or implements a fix
  -> tests and verification gates run
  -> fix is deployed or rejected
  -> deployment result is logged
  -> the next runtime cycle continues with better evidence
```

Any implementation of this change should therefore include repair and deploy lifecycle requirements, not only raw file logging.
