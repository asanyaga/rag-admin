# Secret Rotation Guide

## When to Rotate Secrets

Rotate your secrets only in these situations:

### 1. Security Breach
- Secrets were exposed (committed to Git, leaked in logs, etc.)
- Server was compromised
- Unauthorized access detected

### 2. Planned Maintenance
- Compliance requirements (e.g., annual rotation)
- Staff changes (departing employees had access)
- Best practice periodic rotation (e.g., every 6-12 months)

### 3. Initial Setup
- First time deploying the application

## What NOT to Do

❌ **DO NOT** regenerate secrets during normal updates/deployments
❌ **DO NOT** change secrets without a specific reason
❌ **DO NOT** rotate secrets without planning for the impact

## Impact of Rotating Secrets

### JWT_SECRET_KEY
**Impact**: All JWT tokens become invalid immediately
- ✅ Effect: All users are logged out
- ✅ Users must sign in again
- ⚠️ API clients using tokens will fail until they get new tokens

**Mitigation**:
- Notify users in advance
- Consider dual-key validation during transition (advanced)
- Schedule during low-traffic period

### SESSION_SECRET_KEY
**Impact**: All session cookies become invalid immediately
- ✅ Effect: All users are logged out
- ✅ Users must sign in again
- ⚠️ Any in-progress operations may be lost

**Mitigation**:
- Same as JWT_SECRET_KEY
- Coordinate with JWT rotation if possible

### POSTGRES_PASSWORD
**Impact**: Database connection breaks immediately
- ❌ Application crashes
- ❌ All services stop working
- ⚠️ Requires database password change AND application restart

**Mitigation**:
- More complex - requires database coordination
- See "PostgreSQL Password Rotation" section below

## How to Rotate Secrets Safely

### Step 1: Plan & Notify
```
1. Choose low-traffic time (e.g., 2 AM Sunday)
2. Notify users of planned maintenance
3. Estimate downtime (5-10 minutes)
4. Have rollback plan ready
```

### Step 2: Generate New Secrets
```bash
# Generate new secrets (save output)
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('SESSION_SECRET_KEY=' + secrets.token_urlsafe(48))"
```

### Step 3: Backup Current Configuration
```bash
# On VPS
cd ~/rag-admin
cp .env.prod .env.prod.backup.$(date +%Y%m%d)
```

### Step 4: Update .env.prod
```bash
# Edit configuration
nano .env.prod

# Update:
# - JWT_SECRET_KEY=<new-value>
# - SESSION_SECRET_KEY=<new-value>
# Keep POSTGRES_PASSWORD unchanged for now
```

### Step 5: Restart Services
```bash
# Restart backend to load new secrets
docker compose -f docker-compose.prod.yml restart backend

# Verify services are healthy
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend | tail -20
```

### Step 6: Verify
```bash
# Test sign-in works with new secrets
curl -X POST https://yourdomain.com/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'

# Should get new JWT token
```

### Step 7: Update Backup
```bash
# Save new .env.prod to password manager
# Delete old backup after confirming everything works
rm .env.prod.backup.*
```

## PostgreSQL Password Rotation

Rotating the database password is more complex:

### Method 1: Change Password in PostgreSQL (Recommended)

```bash
# Step 1: Enter PostgreSQL container
docker compose -f docker-compose.prod.yml exec postgres psql -U ragadmin -d ragadmin

# Step 2: Change password in PostgreSQL
ALTER USER ragadmin WITH PASSWORD 'new-secure-password';
\q

# Step 3: Update .env.prod with new password
nano .env.prod
# Update POSTGRES_PASSWORD=new-secure-password
# Update DATABASE_URL=postgresql+asyncpg://ragadmin:new-secure-password@postgres:5432/ragadmin

# Step 4: Restart backend
docker compose -f docker-compose.prod.yml restart backend

# Step 5: Verify connection works
docker compose -f docker-compose.prod.yml logs backend | grep -i database
```

### Method 2: Full Database Restart (More Disruptive)

```bash
# Step 1: Backup database
~/rag-admin/backup.sh

# Step 2: Stop all services
docker compose -f docker-compose.prod.yml down

# Step 3: Update .env.prod with new POSTGRES_PASSWORD
nano .env.prod

# Step 4: Start services (database will initialize with new password)
# WARNING: This may lose data if not careful!
docker compose -f docker-compose.prod.yml up -d

# Step 5: Restore from backup if needed
```

**⚠️ Warning**: Method 2 can cause data loss. Use Method 1.

## Rollback Plan

If something goes wrong after rotation:

### Quick Rollback
```bash
# On VPS
cd ~/rag-admin

# Restore old configuration
cp .env.prod.backup.YYYYMMDD .env.prod

# Restart services
docker compose -f docker-compose.prod.yml restart backend

# Verify
docker compose -f docker-compose.prod.yml ps
```

### Full Rollback
```bash
# If database was affected
docker compose -f docker-compose.prod.yml down

# Restore old .env.prod
cp .env.prod.backup.YYYYMMDD .env.prod

# Restore database from backup
gunzip -c ~/backups/ragadmin_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U ragadmin -d ragadmin

# Restart services
docker compose -f docker-compose.prod.yml up -d
```

## Best Practices

### Secret Storage
- ✅ Store secrets in password manager (1Password, Bitwarden)
- ✅ Encrypt backups of .env.prod
- ✅ Limit access to production secrets
- ✅ Use different secrets for dev/staging/production
- ❌ Never commit .env.prod to Git
- ❌ Never share secrets via email/Slack
- ❌ Never store secrets in plain text notes

### Rotation Schedule
- **JWT/Session Secrets**: Every 6-12 months (or on security event)
- **Database Password**: Every 12 months (or on security event)
- **After staff changes**: When employees with access leave
- **Compliance**: Follow your organization's requirements

### Monitoring
- Monitor for failed authentication after rotation
- Check error logs for connection issues
- Verify backup still works with new password
- Test API endpoints after rotation

### Documentation
- Document when secrets were last rotated
- Keep audit log of rotation events
- Note who performed rotation and why
- Record any issues encountered

## Automation (Advanced)

For production systems, consider:

- **Secrets Management**: HashiCorp Vault, AWS Secrets Manager
- **Automated Rotation**: Rotate secrets automatically on schedule
- **Zero-Downtime**: Dual-key validation during transition
- **Audit Logging**: Track all secret access and changes

## Emergency Secret Rotation

If secrets are compromised and you need immediate rotation:

```bash
# 1. Generate new secrets NOW
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# 2. Update .env.prod immediately
nano .env.prod

# 3. Restart services
docker compose -f docker-compose.prod.yml restart backend

# 4. Notify all users
# Send email: "For security, all users have been logged out. Please sign in again."

# 5. Monitor for suspicious activity
docker compose -f docker-compose.prod.yml logs -f backend

# 6. Review logs for unauthorized access
# 7. Investigate how secrets were compromised
# 8. Fix the root cause
```

## Summary

**Key Takeaway**: Secrets are generated ONCE during initial setup and then:
- Stored securely in password manager
- Backed up in encrypted form
- Rotated only when necessary (security event or scheduled maintenance)
- Never regenerated during normal deployments

Normal deployments reuse the existing `.env.prod` file without changes.
