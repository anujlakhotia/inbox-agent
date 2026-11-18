# Evals for the Ask agent

The Ask tab is a retrieval agent over email, so the eval has two levels. Both use a **synthetic mailbox** (61 invented
emails, 31 of them planted with known facts), never real mail, so everything here is safe to publish and re-run.

| Level | Command | Cost | Measures |
|---|---|---|---|
| 1. Retrieval | `python -m evals.retrieval` | **free**, no API key | Does the search find the right emails? Is the expected fact inside the part of the email the agent can read? |
| 2. End to end | (planned) | tokens | Is the answer correct, grounded, honest about missing info, and resistant to injected instructions? |

Level 1 sets `DB_PATH` to a throwaway database and removes `ANTHROPIC_API_KEY` from its environment before it imports
anything, and it refuses to run if the database path is not the throwaway one.

## Files

- `mailbox.py`: the synthetic emails (dates are "days ago", so the mailbox always looks recent).
- `cases.py`: the 25 questions, with their checks (`must`, `any`, `must_not`, `rubric`, `min_recall`).
- `CASES.md`: the cases rendered for human review (`python -m evals.render_cases`, which also validates the set).
- `results/retrieval.md`: the latest level-1 result.

## Reading the level-1 numbers

- The query is the question's content words, a proxy for what the agent types. The real agent rewrites its searches,
  so "search" misses on vocabulary cases are pessimistic.
- A case is a hit when all gold emails (or `min_recall` of them) are in the top 8 results.
- "Fact readable" asks whether the expected string is within the first 4,000 characters of the cleaned body, which is
  all `read_email` returns. A "NO" here means the agent cannot answer that question however well it searches.
- It cannot judge answers, abstention or injection resistance. Those need level 2.
