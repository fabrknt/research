You run one turn of the xStocks loop. You start in 2026-11-22-xstocks-depth/loop/ and write only here
(paths below are relative to it; the rest of the repo is ../.. and may be read).

1. Read README.md (the question, the gate, what you may do), findings.md if it exists, and the last
   three notes in experiments/ (newest names sort last).
2. Read the numbers: `python3 -I table.py loop.summary.jsonl`, and with
   `--by day` when a day matters. table.py's docstring defines every column.
3. Pick ONE question the last notes left open or that the new hours raise. Prefer the one that moves the
   gate most. Say why in one line.
4. Answer it with numbers you computed. You may write a small script here and run it with `python3 -I <script>`, one command per call;
   the workflow commits it with the note, so the number can be rerun.
5. Write experiments/<UTC date>T<hour>.md (for example 2026-11-23T18.md):
   - question, why this one
   - what was run (the command lines)
   - result: the numbers, copied from the output, nothing rounded into words
   - what it says for the gate: go on / stop / not settled, and what is missing
   - next question
6. Only when the numbers settle something (enough hours, both sessions where it matters), add one line to
   findings.md: the date, the claim, the command that shows it.

Rules
- Every number you write is a line of an output you ran in this turn. If you could not compute it, write
  "not computed" and why.
- Separate what was measured from what is inferred.
- Saying "no room" or "room" needs the minimal counter-case you looked for and did not find (a name, a
  size, a session).
- Fewer than 24 hours in a session is not enough to settle that session; say so instead.
- Do not edit README.md, prompt.md or table.py (changes to them are thrown away). Read files with the Read
  tool, not cat.
