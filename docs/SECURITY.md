# SECURITY — plans-vision-api

## Secrets and Environment Variables

Secrets MUST NOT be committed to the repository.

Required environment variables (example):
- OPENAI_API_KEY
- STORAGE_ROOT
- DATABASE_URL (or SQLITE_PATH)
- API_KEY_SECRET (or key store config)
- MAX_UPLOAD_BYTES
- MAX_IMAGE_PIXELS
- LOG_LEVEL

## API Key Handling
- API keys are treated as secrets
- Store hashed keys server-side (recommended)
- Never log raw API keys

## Logging Rules
- Never log full request bodies containing user data
- Never log images or base64 blobs
- Mask secrets in logs

## Tenant Isolation
- Every query must include tenant_id or equivalent scoping
- Cross-tenant access is a security bug

## Dependency Security
- Avoid adding dependencies unless required
- Pin major versions where possible
- Run vulnerability scans when available
