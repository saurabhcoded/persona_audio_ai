# Dev workflow (for every task)

1. **Orient**
   - Read `agents/steering.md` and `agents/progress.md`.
   - Find the requirement IDs (`FR-*`) the task covers in `docs/requirements/product-requirements.md`.
   - Read the workflow file for the area you'll touch.
2. **Check decisions**
   - Look in `agents/decisions.md`. If the task needs an undecided choice (OQ-*), ask the user or
     pick the *proposed* default and say so; record it.
3. **Plan small**
   - One milestone sub-item at a time. Prefer a vertical slice (model → service → route → test).
4. **Implement**
   - Follow conventions in `steering.md` (settings, routes, DI for external clients, prompts in one file).
   - New dependency? Add to `requirements.txt` with a lower bound; note in `decisions.md` if non-obvious.
5. **Test**
   - Synthetic fixtures in `tests/fixtures/`. Mock LLM/Fish/embeddings via `app.dependency_overrides`.
   - `make lint && make test`. For guardrail changes, the privacy regression test must pass.
6. **Verify end-to-end** when a route changed: `make run` + curl, or `make web` for UI.
7. **Record**
   - Tick items in `agents/progress.md`, set "next step".
   - Append any decision to `agents/decisions.md`; add gotchas to the relevant workflow/knowledge file.
8. **Report** to the user: what changed (files), requirement IDs, test results, anything skipped.

Commits/PRs only when the user asks.
