# Golden set: first measurement

**Not measured yet.** Measuring needs a real AI key (the questions go to a real model); see `DEFERRED.md`. What exists:

- `golden/questions.json`: 30 draft questions (+ one smoke question) in 9 categories: sales, own data (salesperson), limits, invoices, purchases, point of sale, stock without a hint, honesty. **Please correct it** (add, remove, reword). Questions whose module is not installed in the database are skipped, not failed.
- `scripts/run_golden.py`: asks every question through the real chat as the question's user, then checks what was built (reporting model, measure, the status filter) and the NUMBER against an oracle, a plain Odoo query evaluated at run time on the same database, as the same user. A question that must be refused (`honesty`) passes only if no dashboard is built.
- The runner itself is proven: with the pretend vendor the smoke question F00 passes (the dashboard's total equals Odoo's), comparison logic fails on a 1% difference and on a wrong top list, skipping works.

How to measure once the key is entered:

    python3 scripts/run_golden.py --write notes/F5_golden_v1.md

(the target accuracy is set together, after the first measurement).
