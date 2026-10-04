# M0 acceptance evidence

Verified on 2026-10-04. Scope: **M0 — Repository + Platform Foundation**.
The master instruction and all four locked specifications were read before the
initial implementation. This record supplements the final milestone report;
it does not replace or modify any locked specification.

## Executed gates

The existing implementation was resumed and reviewed without regenerating it.
The complete gate was rerun from the repository root:

```powershell
./scripts/m0-gate.ps1
```

The exact staged source was also exported with `git checkout-index` into a fresh,
ignored directory inside the repository. No virtual environment, node_modules,
existing artifacts, caches or existing `.env` were included. A new local password
was generated in that export's ignored `.env`. The same script ran with:

```powershell
./scripts/m0-gate.ps1 -ProjectName modelmedic-m0-resume-clean -ApiPort 18002 -FrontendPort 15175
```

That Compose project created fresh PostgreSQL and artifact volumes. Both full
gate runs completed with their success marker after all required commands passed.
The clean-export command wrapper initially looked for its display log relative to
the directory changed by the script; the actual log was then read by absolute path
and confirmed the full gate had completed successfully.

## Results

| Check | Executed result |
|---|---|
| Compose configuration | Validated with `config --quiet` |
| Image builds | Backend, frontend and test images built successfully |
| Locked installs | Docker builds used `uv sync --locked` and `npm ci` |
| Empty database | Explicit `alembic upgrade head` succeeded with fresh volumes |
| Schema consistency | ORM metadata matched migrated schema; revision `0001_m0` |
| API / worker / frontend / PostgreSQL | All four services started; API and PostgreSQL healthy |
| Ruff lint | `ruff check --no-cache backend migrations scripts` passed |
| Ruff formatting | `ruff format --check --no-cache backend migrations scripts` passed |
| Python typing | `mypy --cache-dir /tmp/mypy` passed: 24 source files |
| Backend tests | `pytest -q -p no:cacheprovider`: 23 passed, no skips |
| Frontend lint | `npm run lint` passed |
| Frontend typing | `npm run typecheck` passed |
| Frontend tests | `npm run test`: four passed |
| Production frontend build | `npm run build` passed |
| Dependency audit | `npm audit --audit-level=low`: zero vulnerabilities |
| Compose smoke | `python -m scripts.smoke` passed |

The smoke check reached `/api/v1/health/ready` through the Compose-internal
`http://frontend:5173` hostname, proving Vite's explicit hostname allowlist works.
It also verified liveness, readiness, frontend reachability, a recent worker
heartbeat, successful dummy-job completion observed through the API, and the
active-job uniqueness constraint.

PostgreSQL integration tests exercised job creation, duplicate prevention,
`SKIP LOCKED`, concurrent claims, committed claims before computation, periodic
heartbeat renewal, expired-lease recovery, retry exhaustion, ownership fencing,
double-finalization rejection, sanitized failure and incompatible-schema rejection.
The suite created, migrated and removed its own uniquely named test database.
LocalArtifactStore tests passed for reads, writes, deletion, scoped prefix deletion,
write-once behavior and invalid-key rejection.

An additional running-stack check wrote a harmless artifact from the API container,
read and deleted it from the worker container, and confirmed matching API/worker
image IDs. Earlier browser verification covered navigation, route focus and
320px menu/reflow; the resumed gate reran the frontend component tests.

## Repository review

`scripts/privacy_check.py`, manual staged-diff review, `git diff --cached --check`
and the comparison against `8e2029a` were performed. No credentials, personal email,
private datasets, model artifacts, database contents, dependency directories or
unrelated files were found among commit candidates. `.env` and generated outputs
remain ignored. All four files in `docs/specs/` remain unchanged.

No M1 functionality or scientific computation was implemented. Project creation
remains disabled and the ML package is a placeholder. No locked-decision conflict
was discovered. Commit, push, remote containment and post-commit clean-tree results
are recorded in the final milestone report rather than embedding a self-referential
commit hash here.

## Non-blocking limitation

The backend suite emits one upstream Starlette TestClient warning about its
`httpx` compatibility path. All tests pass; there are no unresolved M0 gate failures.
