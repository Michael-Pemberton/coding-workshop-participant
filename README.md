# Coding Workshop — Project Management App

A small project/portfolio management application built as a coding workshop
exercise. Tracks projects, people, assignments, deliverables, and budgets,
with computed RAG (red/amber/green) health that propagates across project
and deliverable dependencies.

The app deploys to AWS (Lambda + API Gateway + S3 + CloudFront + Aurora
PostgreSQL) and can also be run locally against LocalStack.

---

## Repository layout

```
backend/        Python Lambda functions (one per entity)
frontend/       React + Vite + MUI single-page app
infra/          Terraform for AWS resources
bin/            Deploy, init, and local-dev scripts
ENVIRONMENT.config   Per-participant config (generated)
```

---

## Tech stack

| Layer       | Tech                                                                  |
| ----------- | --------------------------------------------------------------------- |
| Frontend    | React 19, Vite, Material-UI 5, react-router-dom, axios                |
| Backend     | Python 3.11 AWS Lambda handlers, psycopg, PyJWT                       |
| Database    | PostgreSQL (Aurora on AWS; local Postgres for dev)                    |
| Infra       | Terraform — Lambda, API Gateway, S3, CloudFront, RDS, IAM             |
| Local dev   | LocalStack (AWS emulator), Vite dev server, optional Node proxy       |
| Auth        | JWT (24h expiry), role-based access control                           |

---

## Domain model

| Entity        | Notes                                                                   |
| ------------- | ----------------------------------------------------------------------- |
| Project       | Title, dates, budget, status, health, `dependency_ids` (UUID[])         |
| Person        | Name, email, capacity (hrs/week), hourly pay                            |
| Assignment    | Person ↔ project + role + hours/week                                    |
| Deliverable   | Title, due date, optional `depends_on_id` (another deliverable)         |
| Budget item   | Per-project line items by category, planned vs consumed                 |
| Staff budget  | Auto-derived per-person costs with optional manual overrides            |
| User          | Login credentials + role (`admin`, `manager`, `contributor`, `viewer`)  |

### RAG health

- Time bands: green > 5 days, amber 1–5 days, red ≤ 1 day or overdue.
- Projects also factor budget consumed/planned (green < 70%, amber 70–95%, red > 95%).
- **Dependency propagation** (both deliverables and projects):
  - A prerequisite's worse time-band worsens its dependant (forward).
  - A dependant's worse time-band worsens its prerequisite, since the
    prerequisite is effectively due by the dependant's date (reverse).
  - Messages show the propagated band, e.g. `red due to dependant due in 3 day(s)`.

### Roles & scoping

| Role          | Capabilities                                                          |
| ------------- | --------------------------------------------------------------------- |
| admin         | Full CRUD on everything, user admin                                   |
| manager       | Full CRUD on entities (no user admin)                                 |
| contributor   | Create/update on projects they're assigned to                         |
| viewer        | Read-only on projects they're assigned to                             |

Scoped roles (`viewer`, `contributor`) only see projects to which they
have an `assignments` row. Enforced server-side in
`backend/shared.py::get_scoped_project_ids`.

---

## Frontend pages

| Path                    | Purpose                                                |
| ----------------------- | ------------------------------------------------------ |
| `/login`                | Username/password login                                |
| `/`                     | Dashboard: KPIs, RAG summary, overallocation, recents  |
| `/projects`             | Project list, default-sorted by status                 |
| `/projects/:id`         | Project overview + tabs (people, deliverables, budget) |
| `/people`               | Team list with allocation bars (active projects only)  |
| `/deliverables`         | Per-project or "All deliverables" view, sorted by due  |
| `/budgets`              | Per-project budget tracking + internal-staff section   |
| `/admin/users`          | Admin: user CRUD and role management                   |

Some notable behaviors:

- **Dashboard "Recent Projects"** sorts by per-user, per-project
  last-viewed timestamp (stored in `localStorage`).
- **Project health, over-budget, and overallocation** widgets only count
  active projects; inactive projects' hours don't consume capacity.
- **Inactive projects** are hidden from a person's assignment list
  without losing the record — they reappear when the project reactivates.
- **Project overview tab** lets managers edit status, start date, and
  end date inline (commit on change/blur).
- **Deliverables "All" view** shows every accessible deliverable sorted
  by due date with a Project column.

---

## Local development

Requires Docker, Node 18+, Python 3.11, Terraform, AWS CLI, and
LocalStack.

```bash
./bin/start-dev.sh
```

Brings up PostgreSQL, LocalStack, Terraform-managed Lambdas, and the
Vite dev server. Default local DB:
`postgres://postgres:postgres123@localhost:5432/postgres`.

Tear down with `./bin/cleanup-environment.sh`.

---

## Deploying to AWS

Backend (Lambda + API Gateway + RDS) — must run first so Terraform
outputs the API URL the frontend will be built against:

```bash
./bin/deploy-backend.sh aws
```

Frontend (build + S3 sync + CloudFront invalidation):

```bash
./bin/deploy-frontend.sh aws
```

The frontend script reads `terraform output -raw api_base_url` and bakes
it into the Vite build, then prints the CloudFront URL on completion.

Other `bin/` scripts:

| Script                  | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `start-dev.sh`          | Start everything for local dev                       |
| `init-db.sh`            | Run schema DDL against a fresh database              |
| `setup-environment.sh`  | One-shot AWS environment provisioning                |
| `setup-participant.sh`  | Workshop participant init (writes ENVIRONMENT.config) |
| `generate-env.sh`       | Regenerate `.env` files from Terraform outputs       |
| `cleanup-environment.sh`| Destroy all provisioned resources                    |
| `proxy-server.js`       | Optional local API proxy                             |

---

## Backend layout

Each entity is its own Lambda with a `function.py` handler:

```
backend/
  shared.py            DB pool, JWT, RBAC, field allowlists, schema DDL
  auth/function.py     Login, JWT issuance, rate limiting
  projects/function.py CRUD + health propagation
  people/function.py   CRUD + allocation
  assignments/function.py
  deliverables/function.py  CRUD + RAG + forward/reverse dep propagation
  budgets/function.py  CRUD + per-staff totals/overrides
  tests/               Pytest suite
```

Schema is created/migrated on Lambda cold start from DDL in `shared.py`.
Soft deletes (`is_deleted = TRUE`) are used throughout.

---

## Configuration

`ENVIRONMENT.config` is generated by `setup-participant.sh` and consumed
by the deploy scripts. It contains the participant id, AWS region, and
participant Lambda URL.

Vite build vars (`VITE_API_URL`, `VITE_API_ENDPOINTS`) are exported by
the frontend deploy script from Terraform outputs.

---

## License

See [LICENSE](LICENSE). Contributions under the terms in [DCO.md](DCO.md).
