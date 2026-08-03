# Lab: Plan Mode vs Direct Execution

Run both prompts on a disposable branch and compare the transcript, tool use,
diff, and tests.

1. Direct, bounded change: “Add a `discount` argument to `compute_total` and
   add two tests. Implement it now.”
2. Plan-first, ambiguous change: “Redesign pricing so several promotion types
   can compose across the API.” Start with `--permission-mode plan`, inspect the
   proposed file and API changes, then begin a fresh implementation session.

Checkpoint: choose plan mode because scope or architecture is ambiguous, not
merely because a change feels difficult.
