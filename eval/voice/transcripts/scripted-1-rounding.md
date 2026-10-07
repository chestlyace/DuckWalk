# Walk conversation scripted-1-rounding

Started 2026-10-07T13:49:27. Model `gemma4:31b-cloud`, TTS `piper`, STT `ggml-base.en.bin`.

**Duck:** So you're seeing 50.98 instead of 50.97. What part of the rounding logic in the invoice file are you looking at first?

**You:** I've got an invoice test failing, the total comes out as 50.98, but the test expects 50.97.

**Duck:** Got it, 50.98 instead of 50.97. Does that difference happen before or after the discount is applied?

**You:** I think the discount gets rounded for each item and then added up, so each item rounds up a little.

**Duck:** Rounding each item individually. What would happen if you summed the discounts before rounding?

**You:** I haven't checked that yet. The test passes the disk out as a float, not a decimal, which might matter too.

**Duck:** Using floats instead of decimals. Could that be where the precision is shifting?

**You:** The quickest check would be to print each line total before the sum and see where the extra cent appears.

**Duck:** Printing the line totals. Which specific line item do you expect to be the one rounding up?

**You:** Right, so first I'll print the line totals, then try the same test with a decimal discount.

**Duck:** Printing and then trying decimals. Which of those two checks would confirm if the issue is the summation order?

**You:** and walk.

**Duck:** Okay, ending the walk. Nice thinking out there.
