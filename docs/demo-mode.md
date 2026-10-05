# M6 read-only synthetic demo

Full Mode remains the local API + PostgreSQL + worker + private-artifact workflow.
The wire configuration is `MM_DEPLOYMENT_MODE=full` or `demo`; the runtime endpoint
reports the locked names `FULL_MODE` / `DEMO_MODE`. Outside local development,
`MM_ENVIRONMENT=deployment` requires an explicit mode. This adds no authentication,
public port exposure, hosting configuration or M7 deployment pipeline.

## Generate through the real pipeline

From the repository root, with the existing ignored `.env`, choose unused local
ports and an isolated project. The gate handles builds, one explicit migration,
all M0–M5 regression suites, the seed, and the worker-free read-only smoke:

```powershell
./scripts/m6-gate.ps1 -ProjectName modelmedic-m6-verified -ApiPort 18010 -FrontendPort 15183
```

For an already built and migrated Full Mode stack:

```powershell
docker compose -p modelmedic-m6-verified -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.seed_demo create
docker compose -p modelmedic-m6-verified -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.seed_demo verify
```

The test image contains the operator seed utility; the public runtime image has no
seed HTTP endpoint. A deterministic Python generator (seed 4200 + period) creates
1,500 baseline observations and three independent current datasets of 360 rows.
Fields are generic synthetic signal/context/segment/outcome values, with no real
people or private records. Later periods introduce covariate change, missingness,
new categories, and one changed observed relationship for educational inspection.
They are illustrative observations, not claims about a deployed real-world model.

The utility creates the project through the API, uploads streamed CSV bodies,
waits for PostgreSQL validation jobs, configures Logistic Regression / Standard,
trains through the actual baseline worker, establishes the baseline, and analyzes
a B–A–B history through the actual monitoring worker. Both labeled runs receive
separate categorical slices. Reports are saved in Full Mode before publication.
Nothing writes fabricated scientific result tables.

Only after all jobs succeed does the utility publish the private `demo/seed.json`
registry containing exact project/run/job/slice IDs, source SHA-256 values,
method/schema/artifact/report versions and output fingerprints. Source CSVs,
canonical Parquet, fitted artifacts, reports and the registry stay in the ignored
runtime artifact volume. They are never checked into Git.

## Read-only topology and scope

```powershell
docker compose -p modelmedic-m6-verified -f compose.yaml stop worker
docker compose -p modelmedic-m6-verified -f compose.yaml -f scripts/compose.demo.yaml up -d --wait postgres api frontend
docker compose -p modelmedic-m6-verified -f compose.yaml -f scripts/compose.demo.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.smoke_m6
```

The override mounts the API's artifact volume read-only. Demo readiness checks
PostgreSQL/schema and the seed registry, with no worker requirement. All non-GET
requests are denied with HTTP 403, including HEAD and OPTIONS. GET requests require
an explicit reviewed route and registered synthetic identifiers. The project list
excludes unrelated projects. An unregistered route is denied, a non-seed resource
is not found, and a missing/incompatible/changed seed fails closed. Reports must
already exist; a GET never queues an analysis or creates a missing report.

The UI displays `READ-ONLY DEMO`, `Synthetic demo data`, and the exact educational
explanation on prohibited actions. Direct API requests remain denied even if the
frontend is bypassed. The real-stack smoke enumerates every API-schema path against
all prohibited methods and checks row counts and result fingerprints before and
after requests/restart.

## Restore Full Mode or regenerate

Use the base Compose file (without the demo override) to recreate API and worker:

```powershell
docker compose -p modelmedic-m6-verified -f compose.yaml up -d --wait api worker frontend
```

After a scientific methodology/schema/artifact/report version changes, explicitly
regenerate in Full Mode:

```powershell
docker compose -p modelmedic-m6-verified -f compose.yaml -f scripts/compose.test.yaml run --rm --no-deps -T api python -m scripts.seed_demo regenerate
```

Regeneration removes only the exact operator-registered synthetic project and its
runs/private prefix, after verifying the project identity and run ownership. It
does not discover or remove projects by name alone. UUIDs/timestamps naturally
change, while generated source bytes and science remain reproducible for the same
versions. `create` refuses to overwrite a completed registry. If interrupted
before publication, the seed remains unpublished; inspect the isolated Full Mode
stack and finish cleanup before reseeding rather than admitting partial outputs.

## Review surfaces

Open the localhost frontend and select the synthetic project. Baseline Results,
Period 2 Mode A Overview, Data / Feature Detail, Period 3 Mode B Performance,
Calibration, and Trends form the six portfolio views. All displayed values come
from the actual persisted pipeline outputs. The report's print preview uses the
same stylesheet as browser print. Native print-dialog and physical paper pagination
remain a final manual M7 check; no server PDF engine is introduced.
