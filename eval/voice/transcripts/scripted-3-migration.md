# Walk conversation scripted-3-migration

Started 2026-10-07T13:51:58. Model `gemma4:31b-cloud`, TTS `piper`, STT `ggml-base.en.bin`.

**Duck:** You were seeing an integrity error with null values in archived at. What did you expect that default value to be?

**You:** My Django migration fails on my local database, it says a column contains null values when I add archive that.

**Duck:** A null value in archived at. Did you specify a default value for existing rows in migration fourteen?

**You:** I added the field as not null without a default, the table already has rows in it, so that must be the problem.

**Duck:** So the table already has rows. What is the smallest change you could make to that migration to handle those existing rows?

**You:** I think the existing rows have nothing to put in the new column, I'm not sure how the migration is supposed to handle that.

**Duck:** You are unsure how the migration handles existing rows. What happens if the field is allowed to be null initially?

**You:** I could check whether the production table has rose too, because this will fail the same way.

**Duck:** Checking the production table for rows. If it does have rows, how would that change your approach to the migration?

**You:** So I need to decide what value old rows should get before I decide how the field is defined.

**Duck:** Deciding on a value for old rows. What would be the most logical value for a project that was not yet archived?

**You:** and walk.

**Duck:** Okay, ending the walk. Nice thinking out there.
