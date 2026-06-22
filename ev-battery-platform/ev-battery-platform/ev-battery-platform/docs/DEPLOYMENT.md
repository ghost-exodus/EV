# EV Battery Telemetry & Diagnostics Platform — Deployment Guide

This guide documents the prerequisites, configuration, and step-by-step instructions for deploying the EV Battery Telemetry & Diagnostics Platform to staging and production environments.

---

## 1. Prerequisites

Before starting, ensure the host machine has the following tools installed:
* **Docker Engine** (v20.10 or higher) and **Docker Compose** (v2.0 or higher)
* **Python** (v3.10 or higher, for scripts and manual migrations if run from host)

---

## 2. Environment Configuration

Create a `.env` file in the project root directory. Here is a description of the required environment variables:

```env
# --- TimescaleDB/PostgreSQL ---
POSTGRES_USER=ev_user
POSTGRES_PASSWORD=ev_password
POSTGRES_DB=ev_telemetry
DATABASE_URL=postgresql://ev_user:ev_password@postgres:5432/ev_telemetry

# --- Security & Auth ---
INTERNAL_API_KEY=super_secret_internal_api_key_123
RATE_LIMIT_RULE=100/minute

# --- SQS (Production vs Local Stack) ---
# For local dev/mock:
SQS_ENDPOINT_URL=http://elasticmq:9324
SQS_QUEUE_URL=http://elasticmq:9324/000000000000/ev-telemetry.fifo
SQS_DLQ_URL=http://elasticmq:9324/000000000000/ev-telemetry-dlq.fifo
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=mock_key
AWS_SECRET_ACCESS_KEY=mock_secret
CREATE_QUEUES_ON_STARTUP=true
```

### Production SQS Configuration
In **production**, do NOT use the local ElasticMQ mock container. Instead, set up AWS SQS FIFO queues and configure:
1. `CREATE_QUEUES_ON_STARTUP=false` (queues should be provisioned via Terraform/CloudFormation).
2. Set `SQS_QUEUE_URL` and `SQS_DLQ_URL` to the active AWS SQS HTTPS endpoint URLs.
3. Remove or leave `SQS_ENDPOINT_URL` blank (so `boto3` defaults to real AWS endpoints).
4. Supply valid AWS IAM credentials via `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or rely on IAM Roles/IAM Instance Profiles if running inside AWS ECS/EKS).

---

## 3. Step-by-Step Deployment

Follow these steps to run the platform locally or in a containerized environment:

### Step 1: Generate Cryptographic Keys
Run the key generator script to create the RSA keypair for RS256 token signing:
```bash
python scripts/generate_keys.py
```
This generates `private_key.pem` and `public_key.pem` in the root directory.

### Step 2: Build and Run Services
Use Docker Compose to build and launch all containers (PostgreSQL, ElasticMQ, and FastAPI):
```bash
docker compose up -d --build
```

### Step 3: Run Database Migrations
Apply Alembic migrations to build the schema, enable TimescaleDB hypertables, concurrent indexes, and compression policies:
```bash
docker compose exec fastapi alembic upgrade head
```

### Step 4: Verify Liveness and Readiness
Check that the platform is healthy and ready to accept traffic:
```bash
# Liveness Check
curl http://localhost:8000/health

# Readiness Check (verifies DB connection and SQS reachability)
curl http://localhost:8000/ready
```
If successful, `/ready` returns `200 OK` with:
`{"status":"ready","db":"connected","sqs":"reachable"}`

---

## 4. Operational Runbooks

### JWT Key Rotation
To rotate JWT signature keys in production without invalidating existing, unexpired access tokens:
1. Run the key rotation script:
   ```bash
   python scripts/rotate_keys.py
   ```
   This archives the current public key inside `previous_keys/` and generates a fresh keypair in the root directory.
2. Redeploy/restart the FastAPI container so that the application loads the new keys.
3. Tokens signed before key rotation will continue to decode successfully using the archived keys inside `previous_keys/` until they expire naturally.

### Database Backups
To perform a complete dump and restore test verifying PostgreSQL/TimescaleDB data consistency:
```bash
bash scripts/backup_restore_test.sh
```
The script runs `pg_dump` with `--no-owner` (preserving TimescaleDB hypertables and continuous aggregates), restores it into a temporary database, and verifies that the row counts of all core tables match the source database.

---

## 5. Troubleshooting

* **FastAPI logs show: `Error: pg_config executable not found`**
  * *Cause:* Trying to build the `psycopg2` package from source.
  * *Fix:* Ensure you are installing the pre-compiled `psycopg2-binary` package, or install the Postgres dev package on the system (`apt-get install libpq-dev` or equivalent).

* **Readiness probe returns `503 Service Unavailable` with `"sqs": "unreachable"`**
  * *Cause:* The SQS mock queue was not initialized or the container port `9324` is blocked.
  * *Fix:* Check SQS logs using `docker compose logs elasticmq`. Ensure `CREATE_QUEUES_ON_STARTUP=true` is set in local development to automatically provision queues.

* **Alembic migration fails with `active transaction block` error**
  * *Cause:* Certain TimescaleDB functions (like compression policy configuration) and Postgres operations (like `CONCURRENTLY` indexing) cannot run inside a standard transaction block.
  * *Fix:* In the Alembic migration file, ensure `disable_ddl_transaction = True` is declared at the module level.
