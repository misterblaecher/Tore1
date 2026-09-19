# Security CI

The repository runs a dedicated security workflow on pull requests and on `main`.

It covers:
- CodeQL for Python and JavaScript/TypeScript;
- `pip-audit` against the pinned backend requirements;
- `npm audit --audit-level=high` against both Node lockfiles;
- Gitleaks secret scanning over Git history.

High/critical dependency findings are blocking by default. Suppressions must be narrow,
versioned in the repository, include a rationale and owner, and be removed when the
underlying finding is fixed. Do not use blanket ignore flags.
