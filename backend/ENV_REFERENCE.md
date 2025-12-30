# PROVENIQ Properties - Environment Variables Reference

This document lists all environment variables used by the PROVENIQ Properties backend.

**CRITICAL:** Never commit actual secrets to git. Use this as a reference only.

---

## Required Variables

### Database

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string with asyncpg driver | `postgresql+asyncpg://user:password@host:5432/dbname` |

### Firebase Authentication

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `FIREBASE_PROJECT_ID` | ✅ Yes | Firebase project identifier | `proveniq-prod-12345` |
| `GOOGLE_APPLICATION_CREDENTIALS` | ⚠️ Conditional | Path to Firebase service account JSON file (required for local dev, use Railway secrets in production) | `/app/firebase-service-account.json` |

### Storage Provider

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `STORAGE_PROVIDER` | ✅ Yes | Cloud storage provider (`gcs` or `s3`) | `gcs` |

#### If `STORAGE_PROVIDER=gcs`:

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `GCS_BUCKET_NAME` | ✅ Yes | Google Cloud Storage bucket name | `proveniq-properties-evidence-prod` |
| `GCS_PROJECT_ID` | ✅ Yes | Google Cloud project ID | `proveniq-prod-12345` |

#### If `STORAGE_PROVIDER=s3`:

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `S3_BUCKET_NAME` | ✅ Yes | AWS S3 bucket name | `proveniq-properties-evidence-prod` |
| `AWS_ACCESS_KEY_ID` | ✅ Yes | AWS access key ID | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | ✅ Yes | AWS secret access key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | ❌ No | AWS region (defaults to `us-east-1`) | `us-west-2` |

### CORS Configuration

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `ALLOWED_ORIGINS` | ✅ Yes | Comma-separated list of allowed CORS origins. **NEVER use `*` in production.** | `https://app.proveniq.io,https://admin.proveniq.io` |

---

## Optional Variables

### Application Configuration

| Variable | Required | Purpose | Default | Example |
|----------|----------|---------|---------|---------|
| `APP_NAME` | ❌ No | Application display name | `PROVENIQ Properties` | `PROVENIQ Properties` |
| `DEBUG` | ❌ No | Enable debug mode (disables in production) | `false` | `true` |
| `API_V1_PREFIX` | ❌ No | API route prefix | `/v1` | `/api/v1` |

### Upload Configuration

| Variable | Required | Purpose | Default | Example |
|----------|----------|---------|---------|---------|
| `PRESIGN_TTL_SECONDS` | ❌ No | Presigned URL expiration time (seconds) | `300` | `600` |
| `MAX_UPLOAD_SIZE_MB` | ❌ No | Maximum file upload size (megabytes) | `50` | `100` |

### Mason AI

| Variable | Required | Purpose | Default | Example |
|----------|----------|---------|---------|---------|
| `MASON_ENABLED` | ❌ No | Enable Mason AI advisory features | `true` | `false` |

### ClaimsIQ Integration

| Variable | Required | Purpose | Default | Example |
|----------|----------|---------|---------|---------|
| `CLAIMSIQ_ENABLED` | ❌ No | Enable ClaimsIQ integration | `false` | `true` |
| `CLAIMSIQ_BASE_URL` | ⚠️ Conditional | ClaimsIQ API base URL (required if enabled) | `http://localhost:3005` | `https://claimsiq.proveniq.io` |
| `CLAIMSIQ_API_KEY` | ⚠️ Conditional | ClaimsIQ API key (required if enabled) | - | `service_claimsiq_prod_abc123` |

---

## Production Deployment (Railway)

### Railway-Specific Variables

Railway automatically provides:

| Variable | Purpose |
|----------|---------|
| `PORT` | Port the application should listen on (Railway assigns dynamically) |
| `RAILWAY_ENVIRONMENT` | Environment name (`production`, `staging`, etc.) |
| `RAILWAY_SERVICE_NAME` | Service name in Railway |

### Setting Variables in Railway

1. Go to Railway dashboard → Your project → Variables
2. Add each required variable from the table above
3. For `GOOGLE_APPLICATION_CREDENTIALS`:
   - Upload the JSON file as a Railway secret
   - Set the variable to the path where Railway mounts it (e.g., `/app/firebase-service-account.json`)

### Production Checklist

- [ ] `DATABASE_URL` points to production PostgreSQL instance
- [ ] `FIREBASE_PROJECT_ID` is the production Firebase project
- [ ] `STORAGE_PROVIDER` is configured (`gcs` or `s3`)
- [ ] Storage credentials are set (GCS or S3)
- [ ] `ALLOWED_ORIGINS` contains **only** production domains (no `*`)
- [ ] `DEBUG` is set to `false`
- [ ] Firebase service account JSON is uploaded as Railway secret
- [ ] All secrets are stored in Railway dashboard (not in `.env` files)

---

## Local Development

Copy `.env.example` to `.env` and fill in your local values:

```bash
cp .env.example .env
```

Then edit `.env` with your local configuration.

**NEVER commit `.env` to git.**

---

## Validation

The application validates all required environment variables at startup.

To test validation without starting the server:

```bash
python -m app.core.env_validation
```

If validation fails, the application will exit with code 1 and display missing/invalid variables.

---

## Security Notes

1. **Never commit secrets to git**
   - `.env` files are in `.gitignore`
   - Use Railway dashboard for production secrets
   - Use environment variables for CI/CD

2. **CORS in production**
   - Never use wildcard `*` in `ALLOWED_ORIGINS`
   - The application will refuse to start if `*` is detected in production mode

3. **Firebase credentials**
   - Store service account JSON outside the repository
   - Use Railway secrets for production
   - Rotate credentials if exposed

4. **Database credentials**
   - Use strong passwords
   - Restrict network access to database
   - Use SSL/TLS connections in production

---

## Troubleshooting

### Application won't start

Run validation manually:
```bash
python -m app.core.env_validation
```

This will show exactly which variables are missing or invalid.

### CORS errors in browser

1. Check `ALLOWED_ORIGINS` includes your frontend domain
2. Ensure no trailing slashes in origins
3. Verify protocol matches (`http://` vs `https://`)

### Storage upload failures

1. Verify `STORAGE_PROVIDER` matches your configuration (`gcs` or `s3`)
2. Check bucket name and credentials
3. Ensure bucket exists and has correct permissions
