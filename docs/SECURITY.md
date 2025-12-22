# SECURITY — plans-vision-api

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it privately rather
than opening a public issue.

---

## Secrets and Environment Variables

Secrets MUST NOT be committed to the repository.

### Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-5.2 | Yes |
| `DATABASE_URL` | Database connection string | No (defaults to SQLite) |

### Optional Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `UPLOAD_DIR` | `./uploads` | Image storage directory |
| `MAX_UPLOAD_SIZE_BYTES` | 10MB | Maximum file upload size |
| `MAX_IMAGE_DIMENSION` | 10000 | Maximum width/height in pixels |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | 60 | Rate limit per tenant |
| `LOG_LEVEL` | INFO | Logging verbosity |

### Best Practices

1. Use `.env` files for local development (gitignored)
2. In production, use secret managers (AWS Secrets Manager, Vault, etc.)
3. Rotate API keys periodically
4. Use least-privilege API key permissions

---

## Authentication

### API Key Authentication (Recommended)

```bash
curl -H "X-API-Key: pv_..." https://api.example.com/projects
```

- Keys are prefixed with `pv_` for identification
- Stored as SHA-256 hashes (never plaintext)
- Invalid keys receive 401 Unauthorized

### Legacy X-Owner-Id (Backwards Compatibility)

```bash
curl -H "X-Owner-Id: <uuid>" https://api.example.com/projects
```

- Supported for backwards compatibility only
- Should be migrated to API key auth

---

## API Key Handling

- API keys are treated as secrets
- Store hashed keys server-side (SHA-256)
- Never log raw API keys
- Key generation: `pv_` + 32 bytes URL-safe base64

---

## Logging Rules

- Never log full request bodies containing user data
- Never log images or base64 blobs
- Mask secrets in logs
- Include tenant_id and request_id for audit trails

---

## Tenant Isolation

- Every query must include tenant_id or equivalent scoping
- Storage paths include tenant_id: `{tenant}/{project}/{file}.png`
- Cross-tenant access is a security bug
- Database queries enforce WHERE tenant_id = ...

---

## File Upload Security

| Protection | Implementation |
|------------|----------------|
| Format validation | PNG magic bytes check (not just extension) |
| Size limit | Configurable, default 10MB |
| Dimension limit | Configurable, default 10000x10000px |
| Path traversal | Resolved paths checked against base directory |
| Storage isolation | Files stored in tenant-scoped directories |

---

## Rate Limiting

- 60 requests/minute per tenant (configurable)
- Fixed window algorithm
- 429 response with Retry-After header

---

## Dependency Security

- Avoid adding dependencies unless required
- Pin major versions where possible
- Run vulnerability scans periodically
- Update dependencies regularly

---

## Production Checklist

- [ ] HTTPS only (terminate TLS at load balancer or reverse proxy)
- [ ] CORS configured for specific origins (not `*`)
- [ ] Rate limiting enabled
- [ ] API key authentication required
- [ ] Secrets in environment variables or secret manager
- [ ] Database backups encrypted at rest
- [ ] Log aggregation with access controls
- [ ] Monitoring and alerting configured
- [ ] File uploads stored outside web root
