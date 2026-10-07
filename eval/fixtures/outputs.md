# Fixture outputs

Model `gemma4:31b-cloud`, generated 2026-10-07 06:22 by `eval/run_fixtures.py`. Prompts: `duckwalk/prompts/summary.txt`, `duckwalk/prompts/nudge.txt`.

| Fixture | Summary words | Within 60? | Nudge words | Summary tokens (in+out) | Nudge tokens (in+out) |
|---|---|---|---|---|---|
| failing_test | 24 | yes | 15 | 430+74 | 364+23 |
| merge_conflict | 26 | yes | 17 | 407+54 | 341+25 |
| flaky_build | 28 | yes | 13 | 418+55 | 352+19 |
| runtime_type_error | 28 | yes | 17 | 396+63 | 330+22 |
| migration_error | 29 | yes | 15 | 360+71 | 294+18 |

## failing_test

_A pytest assertion keeps failing after repeated edits to the same service file._

**Summary** (24 words):

```
Doing: Implementing invoice rounding on branch feat/invoice-rounding.
Failing: tests/test_invoice.py:42 (test_total_with_discount) fails with AssertionError: assert Decimal('50.98') == Decimal('50.97').
Next: Investigate the rounding logic in billing/invoice.py.
```

**Nudge:** Step outside for a short walk to clear your head and solve that test_total_with_discount failure.

**Would you act on it?** [ ] yes  [ ] no

## merge_conflict

_A rebase onto main stopped on conflicts in two files._

**Summary** (26 words):

```
Doing: Applying commit 3f9c2ab to add notification preferences to user settings.
Failing: Merge conflicts in src/models/user.ts and src/api/routes.ts.
Next: Review the conflicts in the open files.
```

**Nudge:** Step outside for a short walk to clear your head and map out the conflicts in src/models/user.ts.

**Would you act on it?** [ ] yes  [ ] no

## flaky_build

_An integration test times out on some runs and passes on others._

**Summary** (28 words):

```
Doing: Implementing order synchronization retries.
Failing: TestOrderSyncRetries in worker_test.go:88 timed out waiting for 3 sync events, got 2.
Next: Investigate why only 2 sync events are being emitted.
```

**Nudge:** Take a short walk to clear your head and solve that TestOrderSyncRetries timeout.

**Would you act on it?** [ ] yes  [ ] no

## runtime_type_error

_The React app crashes on load with an undefined property error after an API change._

**Summary** (28 words):

```
Doing: Implementing dashboard cards in `feat/dashboard-cards`.
Failing: `TypeError: Cannot read properties of undefined (reading 'map')` at `StatsCard.tsx:27:32`.
Next: Investigate why the data being mapped in `StatsCard` is undefined.
```

**Nudge:** Step outside for a short walk to clear your head and solve that map TypeError in StatsCard.tsx.

**Would you act on it?** [ ] yes  [ ] no

## migration_error

_A Django migration fails on the existing local database._

**Summary** (29 words):

```
Doing: Implementing project archiving functionality.
Failing: Applying migration `projects.0014_project_archived` fails with `django.db.utils.IntegrityError` regarding null values in column `archived_at`.
Next: Investigate the default value assigned to `archived_at` in the migration.
```

**Nudge:** Take a quick walk to map out a fix for that IntegrityError in your migration.

**Would you act on it?** [ ] yes  [ ] no
