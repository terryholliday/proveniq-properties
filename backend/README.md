# PROVENIQ Properties - Backend

Unified landlord platform for residential + commercial properties.

## Tech Stack
- **Python 3.11+** with FastAPI
- **PostgreSQL** with SQLAlchemy 2.0 async + asyncpg
- **Firebase Auth** for JWT verification
- **Alembic** for migrations
- **GCS/S3** for evidence storage (provider interface)

## Key Features
- **Immutable Evidence** - SHA-256 hashing, presigned upload + confirm flow
- **Multi-tenancy** - Org-scoped authorization, zero IDOR tolerance
- **Commercial Correctness** - NNN lease validation, sq_ft enforcement
- **Mason AI** - Advisory cost estimation (non-binding)
- **Tenant Privacy** - Landlords cannot view draft inspection evidence

## Setup

### 1. Start PostgreSQL
```bash
docker-compose up -d
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Firebase project ID and storage config
```

### 4. Run Migrations
```bash
python -m alembic upgrade head
```

### 5. Start Server
```bash
uvicorn app.main:app --reload --port 8001
```

## API Documentation
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## API Endpoints (v1)

### Auth
- `POST /v1/auth/magic-link/request` - Request tenant invite
- `POST /v1/auth/magic-link/verify` - Verify token, get Firebase custom token
- `GET /v1/auth/me` - Current user info

### Organizations
- `POST /v1/orgs` - Create org (becomes ORG_OWNER)
- `GET /v1/orgs/me` - Get current org context

### Properties & Units
- `POST /v1/properties` - Create property
- `GET /v1/properties` - List properties
- `POST /v1/properties/{id}/units` - Create unit

### Leases
- `POST /v1/leases` - Create lease (draft)
- `POST /v1/leases/{id}/invite` - Send tenant magic link

### Inspections
- `POST /v1/inspections` - Create inspection
- `POST /v1/inspections/{id}/items` - Upsert items
- `POST /v1/inspections/{id}/evidence/presign` - Get upload URL
- `POST /v1/inspections/{id}/evidence/confirm` - Confirm upload
- `POST /v1/inspections/{id}/submit` - Lock + hash
- `POST /v1/inspections/{id}/sign` - Sign (tenant/landlord)
- `GET /v1/leases/{id}/inspection-diff` - Diff move-in vs move-out
- `GET /v1/leases/{id}/inspection-diff/estimate` - Mason cost estimate

### Vendors & Maintenance
- `POST /v1/vendors` - Create vendor
- `POST /v1/maintenance` - Create ticket
- `PATCH /v1/maintenance/{id}/assign` - Assign vendor/member
- `POST /v1/maintenance/{id}/triage` - Mason AI triage

## Money Rules
All currency stored as **INTEGER CENTS (BIGINT)**:
- `rent_amount_cents`
- `deposit_amount_cents`
- `cam_budget_cents`
- `maintenance_cost_estimate_cents`
- `mason_estimated_repair_cents`

## Non-Negotiables
- Backend is **ASYNC ONLY** (no synchronous DB calls)
- Auth is **Firebase JWT verification** (backend never mints JWTs)
- Inspections are **IMMUTABLE after SIGNED** (corrections = supplemental)
- Mason AI outputs are **ADVISORY ONLY** (never auto-deny, never auto-dispatch)
