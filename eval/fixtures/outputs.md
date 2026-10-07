# Fixture outputs

Model `gemma4:31b-cloud`, generated 2026-10-07 05:55 by `eval/run_fixtures.py`. Prompts: `duckwalk/prompts/summary.txt`, `duckwalk/prompts/nudge.txt`.

| Fixture | Summary words | Within 60? | Nudge words | Summary tokens (in+out) | Nudge tokens (in+out) |
|---|---|---|---|---|---|
| failing_test | 21 | yes | 15 | 430+66 | 364+23 |
| merge_conflict | 23 | yes | 15 | 407+45 | 341+17 |
| flaky_build | 30 | yes | 14 | 418+56 | 352+20 |
| runtime_type_error | 24 | yes | 15 | 396+54 | 330+20 |
| migration_error | 28 | yes | 16 | 360+85 | 294+19 |

## failing_test

_A pytest assertion keeps failing after repeated edits to the same service file._

**Summary** (21 words):

```
Doing: Implementing invoice rounding on branch feat/invoice-rounding.
Failing: test_total_with_discount in tests/test_invoice.py (Decimal('50.98') != Decimal('50.97')).
Next: Investigate the rounding logic in billing/invoice.py.
```

**Nudge:** Step outside for a short walk to clear your head and solve that test_total_with_discount failure.

**Would you act on it?** [ ] yes  [ ] no

## merge_conflict

_A rebase onto main stopped on conflicts in two files._

**Summary** (23 words):

```
Doing: Adding notification preferences to user settings.
Failing: Merge conflicts in src/models/user.ts and src/api/routes.ts.
Next: Review the conflicting changes in the open files.
```

**Nudge:** Step outside for a walk to clear your head and map out those merge conflicts.

**Would you act on it?** [ ] yes  [ ] no

## flaky_build

_An integration test times out on some runs and passes on others._

**Summary** (30 words):

```
Doing: Fixing order synchronization retries.
Failing: TestOrderSyncRetries in worker_test.go:88 timed out waiting for 3 sync events, receiving only 2.
Next: Investigate why the third sync event is not being triggered.
```

**Nudge:** Step outside for a walk to clear your head and solve the TestOrderSyncRetries timeout.

**Would you act on it?** [ ] yes  [ ] no

## runtime_type_error

_The React app crashes on load with an undefined property error after an API change._

**Summary** (24 words):

```
Doing: Implementing dashboard cards on branch feat/dashboard-cards.
Failing: TypeError (reading 'map') at StatsCard.tsx:27:32.
Next: Investigate why the object being mapped in StatsCard.tsx is undefined.
```

**Nudge:** Take a short walk to clear your head and solve that map TypeError in StatsCard.tsx.

**Would you act on it?** [ ] yes  [ ] no

## migration_error

_A Django migration fails on the existing local database._

**Summary** (28 words):

```
Doing: Implementing project archiving via migration 0014.
Failing: `projects.0014_project_archived` fails with `django.db.utils.IntegrityError` regarding null values in column "archived_at".
Next: Investigate the default value or nullability settings in `projects/migrations/0014_project_archived.py`.
```

**Nudge:** Step outside for a walk to clear your head and solve that IntegrityError in your migration.

**Would you act on it?** [ ] yes  [ ] no
