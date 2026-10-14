# M7 operation and Railway deployment

The public read-only demo is deployed at
[ModelMedic Production](https://modelmedic-production.up.railway.app). The operator
completed private seeding, object-store verification and the A4/Letter print gate.
The locked M7 gate still requires actual external verification; local checks alone
are insufficient. Current evidence is recorded in [M7 verification](m7-verification.md).
Stop before M8.

## Local reproducibility

Use Python 3.12, uv 0.11.0, Node 24 and Docker with Linux containers. From the
repository root, copy `.env.example` to the ignored `.env` and replace the local
PostgreSQL password placeholder with a random value. Never paste that file into a
report or commit it. Install with `uv sync --frozen` and `npm ci` in `frontend/`.

The complete fresh gate chooses new disposable PostgreSQL and artifact volumes:

```powershell
./scripts/m7-gate.ps1 -ProjectName modelmedic-m7-check -ApiPort 18011 -FrontendPort 15184
uv run --frozen python scripts/privacy_check.py --history
uv run --frozen python scripts/verify_workflow.py
```

The gate refuses an existing volume set; use a new project name rather than
removing someone else's data. It runs M0–M6 including PostgreSQL tests, migrations,
all 12 training combinations, Full Mode monitoring/slices/reports, clean synthetic
seeding, Demo method enumeration, restart fingerprints, and the actual production
image's same-origin deep links. It ends in local read-only Demo with the worker
and Vite service stopped. The web URL uses the API port at that point.

Full Mode startup/restart waits on PostgreSQL/API/frontend health and verifies
the worker through its actual PostgreSQL heartbeat and an executed dummy job.
The worker has no HTTP healthcheck; it is not included in Compose's `--wait`
service list, which some runner versions reject when image health is disabled.
Worker readiness and all training/analysis/recovery gates remain mandatory.

Backend CI commands are `ruff check backend migrations scripts`, `ruff format
--check backend migrations scripts`, `mypy`, and `pytest -m 'not integration' -q`.
Standalone integration/training also requires actual source provenance:
`MM_CODE_VERSION` must be the current Git SHA, and `MM_CODE_DIRTY` must truthfully
describe the checkout. GitHub Actions sets its exact `${{ github.sha }}` and
`false` for the clean checkout; local Compose gates calculate both values. Never
bypass the unknown-provenance training guard to make tests pass.
For integration, set `TEST_DATABASE_URL` to an isolated PostgreSQL instance, run
`alembic upgrade head`, `alembic check`, and `pytest --require-postgres -m integration
-q`. The integration fixture creates/migrates/drops its own uniquely named database;
it never truncates the supplied database. Its role therefore needs permission to
create disposable databases. Use a test instance, never public production credentials.
On restricted Windows shells, add `--basetemp=.cache/<new-test-directory>`.

Frontend CI runs `npm ci`, `npm run lint`, `npm run typecheck`, `npm run test`,
`npm run build`, and `npm audit --audit-level=low`. The low threshold fails on any
reported vulnerability. Scientific dependencies and npm dependencies remain locked.

`.github/workflows/ci.yml` runs these same commands on Ubuntu 24.04, with a real
PostgreSQL service and a fresh Compose system job after the other jobs pass.
Actions and base images use immutable revisions/digests. Repository guards inspect
all historical blobs and original locked-spec bytes. Native browser/print checks
and production-provider checks are separate operator gates; CI does not pretend to
perform them. Require all four CI jobs in the repository's protected deployment
branch/tag policy before enabling automatic deployments. No deployment workflow
is allowed to run after failed verification.

## Runtime configuration

| Variable | Purpose / required production value |
|---|---|
| `MM_ENVIRONMENT` | `deployment` outside a local rehearsal |
| `MM_DEPLOYMENT_MODE` | `demo` for the public web service; `full` only for isolated private seeding |
| `MM_DATABASE_URL` | Private managed PostgreSQL URL using `postgresql+psycopg`; secret environment value |
| `MM_ARTIFACT_BACKEND` | `s3` in deployment; local development defaults to private filesystem storage |
| `MM_S3_BUCKET` | Actual S3 bucket name from provider credentials, not its display label |
| `MM_S3_ENDPOINT_URL` | HTTPS endpoint for a compatible provider; omit for AWS |
| `MM_S3_REGION` | Provider region; Railway buckets currently use the value in their Credentials tab |
| `MM_S3_PREFIX` | Dedicated private namespace, default `modelmedic` |
| `MM_S3_ADDRESSING_STYLE` | `virtual` by default; use the style required by the bucket's Credentials tab |
| `MM_S3_SERVER_SIDE_ENCRYPTION` | Optional `AES256` request for providers supporting that header; otherwise enforce the provider's encryption-at-rest setting |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN` | SDK environment credentials/role; never Git/build arguments/log output |
| `MM_TRUSTED_HOSTS` | JSON array containing the actual public hostname, `healthcheck.railway.app`, and `127.0.0.1`; add the private seed hostname only to isolated seed services |
| `MM_FRONTEND_ROOT` | Built assets; production image sets `/app/frontend-dist` |
| `MM_ARTIFACT_ROOT` | Set `/artifacts` on every Railway deployment container; private upload scratch remains necessary with S3. The production image also defaults to this non-root writable directory. |
| `PORT` | Provider-assigned listener port; entrypoint and container health check both honor it |
| `MM_OPERATOR_ORIGIN` | Private seed API origin for the operator CLI; no public Full Mode endpoint |
| `CODE_VERSION`, `CODE_DIRTY` | Docker build arguments recording actual Git SHA and dirty/clean state; not secrets |
| `MM_CODE_VERSION`, `MM_CODE_DIRTY` | Runtime provenance when explicitly supplied; never claim clean provenance for an uncommitted candidate |
| `MM_JOB_TIMEOUT_SECONDS` | Wall-clock budget, default 1800 seconds; computation runs in a supervised process |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` | Explicit `1` in the image/CI to prevent nested parallelism |

Initial limits remain 25 MiB uploads, 50,000 rows, 100 input columns, 50 model
features, 100 categories per model feature and 2,000 estimated encoded columns.
The estimate includes the missing category. These are initial guards, not a promise
that all simultaneous maxima complete on every host. See resource evidence in
`m7-verification.md`; timeout failures publish no partial results. Do not increase
limits based on these synthetic measurements.

Full Mode API and worker use the same production backend image. Start commands:

```text
alembic upgrade head
python -m backend.app.web
python -m backend.app.jobs.worker
```

Run Alembic once, explicitly, before either service. API readiness and worker
startup reject incompatible schema; they never migrate concurrently. Web liveness
is `/api/v1/health/live`, readiness `/api/v1/health/ready`, and worker observation
`/api/v1/health/worker`. Demo readiness also checks its versioned private registry
and exact seeded DB scope; it needs no worker. Missing data or later Full Mode
additions to a seeded project close reads rather than expose new rows.

The image runs as uid 10001 and contains built React assets plus the API. Tests,
`.env`, local data, screenshots and caches are absent from its runtime layers.
Private seed/probe CLI modules are shipped in the backend operations package without
exposing HTTP endpoints; the separate `test` target contains test tooling and
compatible local seed wrappers. Default
Docker builds produce the production runtime. There are no production Vite/CORS
services, debug mode, artifact download URLs, user model uploads or joblib loads
in the API. Request IDs and reviewed event messages are logged without uploaded rows.

## Railway Production: reproducible deployment procedure

Target is the user's **ModelMedic / Production** Railway project. Public service
`modelmedic`, PostgreSQL and the private artifact bucket are online. The one-shot
`seed-operator` completed; `seed-api` and `seed-worker` are scaled to zero. Provider
administration is not assumed available to the agent. Required access for future
deployments is an authenticated Railway
session/CLI account with permission to deploy services and configure variables in
that project, plus its private managed PostgreSQL and S3 bucket access. The user
must complete login and any account/security/plan confirmation themselves. Do not
send tokens or passwords in chat. No paid plan is selected by this repository.

Set `MM_ARTIFACT_ROOT=/artifacts` on the web, seed API, seed worker and operator
containers. S3 is the artifact backend; `/artifacts` is still used for temporary
upload files. A relative `artifacts` directory under `/app` is not writable by the
non-root runtime. The production Docker image sets this default, but retain the
explicit Railway variable. `backend.app.web` honors the provider's `PORT`; the
verified Railway deployment uses `8080`. Trust the exact public hostname
`modelmedic-production.up.railway.app`, never a wildcard. Existing seeded results
retain their M6-parent/dirty-candidate provenance; committing M7 does not rewrite
immutable results or imply the deployed image already identifies the new commit.

1. Sign in to Railway and select ModelMedic → Production, or run `railway login`
   and `railway link` selecting that exact project/environment. Ensure the intended
   candidate has passed all local engineering gates. Keep automatic deployment
   disabled until protected-branch CI passes; this initial operator deployment is
   a manual verification of the reviewed working-tree candidate.
2. Provision Railway-managed PostgreSQL and a **private** S3-compatible bucket.
   Keep database access private, public bucket access disabled and all uploaded
   datasets/model artifacts unserved. Configure the table above using secret
   service variables/references. Restrict credentials to this namespace; use a
   read-only object role for the final public Demo where the provider supports it.
   The application itself also rejects every S3 write in Demo Mode.
3. Configure temporary private `seed-api` and `seed-worker` services from the same
   production image, with `MM_ENVIRONMENT=deployment`, explicit `full`, private
   service hostnames in their trusted-host array, and no public domain/ingress.
   Run `alembic upgrade head` once via the API's pre-deploy command. The supplied
   `railway.toml` defines the web command/readiness path and one-shot migration;
   do not configure a second migration command on the worker. Use
   `python -m backend.app.jobs.worker` on the worker and disable its HTTP health
   check. Set real build provenance (`CODE_VERSION` and `CODE_DIRTY`) before build.
   Use `railway up --service seed-api` / `railway up --service seed-worker` to deploy
   the reviewed local candidate when the final milestone is not yet committed.
4. In an ephemeral private operator container using the same production image, supply
   the same private DB/S3 variables, `MM_ENVIRONMENT=deployment`, explicit `full`, and
   `MM_OPERATOR_ORIGIN=http://<private-seed-api-host>:<configured-port>` (no public
   Full Mode endpoint). This container only runs commands and exposes no service.
   Run `python -m backend.app.operations.object_store`, then
   `python -m backend.app.operations.demo_seed create` and
   `python -m backend.app.operations.demo_seed verify`. The probe checks conditional
   write-once behavior and cleans only its unique synthetic prefix. If the
   provider does not support these semantics, stop; never fall back to overwrites.
   The seed must finish baseline training, B–A–B analysis, slices and immutable
   reports before its private registry is published. Never hand-author results.
5. Stop/remove the private Full Mode API and worker after successful verification.
   Deploy `web` using the **production** image, `MM_ENVIRONMENT=deployment`,
   explicit `demo`, private DB/S3 variables and read-only object credentials where
   available. Apply `railway.toml`, set its actual public hostname and Railway
   healthcheck hostname in `MM_TRUSTED_HOSTS`, then enable only this service's public
   HTTPS domain. Its listener uses `PORT`. Never generate a public domain for Full Mode.
6. From outside Railway run `python scripts/smoke_public.py https://<actual-domain>`.
   Confirm the production UI's six views, Mode A/B reports, refresh/deep links,
   exact Demo wording, mutation denial, readiness and `NOT_REQUIRED` worker. Restart
   the web service and repeat. Verify persisted summary/report fingerprints match
   the recorded clean seed. Record the real URL only after this succeeds.
7. Only then is the locked live gate eligible to pass. Complete the final privacy,
   byte-integrity and diff checks; create the single requested M7 milestone commit,
   push to `origin/main`, verify parent/noreply/remote/clean tree. Run the new CI on
   that exact commit before enabling automatic protected-branch deployments. A
   subsequent clean-image deployment preserves immutable previously seeded results
   and their original provenance; do not rewrite them to display a newer code SHA.

Railway currently encrypts buckets at rest but does not support the S3 encryption
request header; use its provider-default encryption, not an unsupported AES256
header. Older buckets may require path-style addressing. Consult its current
[bucket documentation](https://docs.railway.com/storage-buckets). The conditional
write probe remains mandatory regardless of advertised S3 compatibility.
The port and trusted healthcheck hostname above follow Railway's
[healthcheck documentation](https://docs.railway.com/deployments/healthchecks).
Its [pre-deploy command](https://docs.railway.com/deployments/pre-deploy-command)
runs in a separate private container and cannot rely on the API already running;
therefore API-driven seeding is a separate explicit step.

## Final manual print check

On a Mode A report and a Mode B report containing saved slices, use **Print / Save
as PDF** in a full browser. Preview once as A4 portrait and once as Letter portrait,
100% scale with normal margins and background graphics off. Check every page:
navigation and controls absent; headings kept with following content; rows not
clipped; wide tables replaced by complete labeled alternatives; repeated table
headers where supported; black-and-white readable values/statuses; no clipped
content. Save both previews locally outside Git. Native paper pagination is an
explicit operator check when the automation surface cannot access the OS print
dialog. The onscreen preview checks CSS, not physical pagination. No server PDF
generator is added.

The operator has completed all four Mode A/Mode B × A4/Letter previews with these
settings and reported no clipping, overlap, broken sections, pagination defects
or unexpected blank pages. Repeat this procedure if print-related code changes.

## Troubleshooting and carried limits

- A reused M7 gate project fails intentionally: choose an unused project name.
- A failed job with `JOB_TIMEOUT` exceeded its configured wall-clock budget; inspect
  synthetic resource evidence/host allocation, then explicitly retry. SIGTERM
  terminates the computation and leaves an expiring lease for fenced retry after
  restart. A worker losing its token cannot publish. No partial science is exposed.
- An inaccessible/changed seed returns 503. Repair/regenerate through private Full
  Mode; do not broaden the Demo allowlist or edit the registry to admit private rows.
- Failed cleanup can leave an inaccessible private attempt/draft prefix until retry,
  discard or project deletion. The existing after-commit cleanup deliberately never
  removes a newly committed upload when old-prefix deletion fails. Guaranteed
  durable garbage collection would require additional ownership bookkeeping and is
  not introduced as an incidental hardening redesign. Inspect/remove only positively
  identified unreferenced prefixes; never scan-delete by guessed names.
- Artifact hash/version/Python-minor/exact-sklearn errors require compatible internal
  artifacts; never load an untrusted model to bypass the guard.
- A host rejection requires the exact controlled hostname in `MM_TRUSTED_HOSTS`;
  never use `*` for public deployment. Missing DB/bucket secrets are fixed through
  the provider's secret variables, not committed files or logs.

There is no new scientific method, model family, authentication platform, dark
mode, health/risk score, retraining, model serving, streaming, alerting or LLM feature.
