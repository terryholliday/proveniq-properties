# PROVENIQ Properties

**Unified landlord platform for residential + commercial properties.**

Focused on **IMMUTABLE EVIDENCE**, tenant invites, inspection diffs, and maintenance triage. 
Explicitly NOT AppFolio-lite — financials are advisory only.

## Architecture

```
proveniq-properties/
├── backend/          # FastAPI + PostgreSQL
│   ├── app/
│   │   ├── core/     # Config, database, security
│   │   ├── models/   # SQLAlchemy models (14 tables)
│   │   ├── schemas/  # Pydantic schemas
│   │   ├── routers/  # API endpoints
│   │   └── services/ # Business logic
│   └── alembic/      # Database migrations
│
└── frontend/         # Next.js App Router
    └── src/
        ├── app/       # Pages
        ├── components/ # UI components
        └── lib/       # Auth, API client
```

## Tech Stack

### Backend
- Python 3.11+ / FastAPI
- PostgreSQL + SQLAlchemy 2.0 async + asyncpg
- Firebase Admin (JWT verification)
- GCS/S3 (evidence storage)
- Alembic (migrations)

### Frontend
- Next.js 14 (App Router) + TypeScript
- TailwindCSS + shadcn/ui
- TanStack Query
- Firebase Web SDK

## Quick Start

### 1. Start Database
```bash
cd backend
docker-compose up -d
```

### 2. Run Migrations
```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
```

### 3. Start Backend
```bash
uvicorn app.main:app --reload --port 8001
```

### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /v1/orgs | Create organization |
| POST | /v1/properties | Create property |
| POST | /v1/leases | Create lease |
| POST | /v1/leases/{id}/invite | Send tenant invite |
| POST | /v1/inspections | Create inspection |
| POST | /v1/inspections/{id}/submit | Submit inspection |
| POST | /v1/inspections/{id}/sign | Sign inspection |
| GET | /v1/leases/{id}/inspection-diff | Get inspection diff |
| POST | /v1/maintenance | Create ticket |
| POST | /v1/maintenance/{id}/triage | Mason AI triage |

## Non-Negotiables

1. **ASYNC ONLY** - No synchronous database calls
2. **Firebase JWT** - Backend verifies, never mints
3. **Org-scoped** - Zero IDOR tolerance
4. **Money = CENTS** - All currency as BIGINT
5. **Immutable Evidence** - SHA-256 hashed, signed inspections locked
6. **Mason = Advisory** - Never auto-deny, never auto-dispatch

## Domain Model

### Tables (16)
- organizations, users, org_memberships
- properties, units
- leases, tenant_access, bookings
- inspections, inspection_items, inspection_evidence
- turnovers, turnover_photos, turnover_inventory
- vendors, maintenance_tickets
- audit_log, mason_logs

## Ecosystem Integration

- **ClaimsIQ**: Deposit disputes auto-submitted on claim packet generation
- **Capital**: PAY decisions trigger payout settlement

### Key Rules
- Commercial properties REQUIRE `total_leasable_sq_ft`
- Commercial units REQUIRE `sq_ft`
- NNN leases REQUIRE `pro_rata_share_bps`
- SIGNED inspections are IMMUTABLE (corrections = supplemental)

## License
Proprietary - PROVENIQ Technologies
