# Submission status and honest scope

## Included
- FastAPI backend and PostgreSQL schema.
- React/Vite operations dashboard.
- Synthetic data payment generator (expects the master dataset to exist).
- Data dictionary, architecture notes, run instructions, AI-use disclosure.
- Evidence-backed ground-truth labels and a separate validation-test log.
- Test suite and ground-truth integrity checker.

## Verified during packaging
- Python syntax compilation passed.
- Ground-truth checker passed: 2 evidence-backed rows.
- Pytest passed: 4 tests (health route and Pydantic validation). Run used SQLite only for test bootstrapping; no PostgreSQL integration suite was executed in this packaging environment.
- Local development session previously verified PostgreSQL health, API health and dashboard counts as recorded in `docs/validation_report.md`.

## Known incomplete items
- Promise amount greater than arrears and disputed-debt scenarios are not yet reproduced.
- Cross-account payment allocation was rejected with HTTP 422; this is a successful validation test, not a persisted bad allocation.
- A complete deterministic master-data generator and reviewed database export are not included.
- No authentication/authorization, migrations, production monitoring or full integration test suite.
- `docs/AI_USAGE.md` is a concise reconstructed prompt log, not a verbatim complete export. Add the full prompt history from the AI platform before final submission if available.

Do not represent incomplete scenarios or unrun integration tests as completed. The project brief permits partial work when assumptions, limitations and next steps are clearly explained.
