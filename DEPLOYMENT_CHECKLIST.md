# Docker Deployment Checklist

This checklist guides you through deploying RAG Admin to production. Check off each item as you complete it.

## Pre-Deployment (Local Machine)

### 1. Build Frontend
- [ ] Navigate to frontend: `cd frontend`
- [ ] Install dependencies (if needed): `npm install`
- [ ] Build for production: `npm run build`
- [ ] Verify dist directory created: `ls -la dist/`

### 2. Verify Configuration Files
- [ ] Run `./verify-setup.sh` to check all files are present
- [ ] Review `DEPLOYMENT.md` for full deployment guide
- [ ] Review `DOCKER.md` for Docker architecture details

### 3. Update Configuration
- [ ] Edit `caddy/Caddyfile` - replace `yourdomain.com` with your actual domain
- [ ] Commit changes to Git repository (if using Git)
- [ ] Push to remote repository

### 4. DNS Configuration
- [ ] Create A record: `@` → Your VPS IP address
- [ ] Create A record: `www` → Your VPS IP address
- [ ] Wait for DNS propagation (test with `dig +short yourdomain.com`)

## VPS Setup

### 5. Initial Server Setup
- [ ] SSH into VPS: `ssh root@<VPS_IP>`
- [ ] Update system: `apt-get update && apt-get upgrade -y`
- [ ] Install Docker: `curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh`
- [ ] Install Docker Compose: `apt-get install -y docker-compose-plugin`
- [ ] Verify: `docker --version && docker compose version`

### 6. Firewall Configuration
- [ ] Install UFW: `apt-get install -y ufw`
- [ ] Allow SSH: `ufw allow 22/tcp`
- [ ] Allow HTTP: `ufw allow 80/tcp`
- [ ] Allow HTTPS: `ufw allow 443/tcp`
- [ ] Enable firewall: `ufw --force enable`
- [ ] Verify: `ufw status`

### 7. Application User (Optional but Recommended)
- [ ] Create user: `useradd -m -s /bin/bash ragadmin`
- [ ] Add to docker group: `usermod -aG docker ragadmin`
- [ ] Switch user: `su - ragadmin`

## Deployment

### 8. Transfer Code
- [ ] Clone repository: `git clone <repo-url> ~/rag-admin && cd ~/rag-admin`
- [ ] Transfer built frontend from local machine:
  ```bash
  scp -r /home/asa/rag-admin/frontend/dist user@<VPS_IP>:~/rag-admin/frontend/
  ```

  OR

- [ ] Transfer entire project via SCP (includes built frontend):
  ```bash
  scp -r /home/asa/rag-admin user@<VPS_IP>:~/
  ```
- [ ] Verify frontend/dist exists on VPS: `ls -la ~/rag-admin/frontend/dist`

### 9. Environment Configuration (INITIAL DEPLOYMENT ONLY)

> ⚠️ **CRITICAL**: Generate secrets ONCE. Do NOT regenerate on subsequent deployments!

- [ ] Copy template: `cp .env.prod.example .env.prod`
- [ ] Generate secrets **ONE TIME ONLY**:
  ```bash
  python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
  python3 -c "import secrets; print('SESSION_SECRET_KEY=' + secrets.token_urlsafe(48))"
  python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
  ```
- [ ] **Copy the output from above** - you'll need it in the next step
- [ ] Edit `.env.prod`: `nano .env.prod`
  - [ ] Replace `JWT_SECRET_KEY` with generated value (paste from above)
  - [ ] Replace `SESSION_SECRET_KEY` with generated value (paste from above)
  - [ ] Replace `POSTGRES_PASSWORD` in both `DATABASE_URL` and `POSTGRES_PASSWORD` (paste from above)
  - [ ] Replace all `yourdomain.com` with your actual domain
  - [ ] Verify `GOOGLE_CLIENT_ID=disabled` and `GOOGLE_CLIENT_SECRET=disabled`
  - [ ] Set `DEBUG=False`
- [ ] Secure file: `chmod 600 .env.prod`
- [ ] **SAVE BACKUP** of `.env.prod` to password manager or encrypted backup
  - [ ] Store in 1Password, Bitwarden, or similar
  - [ ] Or create encrypted backup: `gpg -c .env.prod`
  - [ ] You MUST be able to recover these secrets if VPS is lost

### 10. Build and Start Services
- [ ] Build images: `docker compose -f docker-compose.prod.yml build`
- [ ] Start services: `docker compose -f docker-compose.prod.yml up -d`
- [ ] Watch logs: `docker compose -f docker-compose.prod.yml logs -f`
- [ ] Wait for SSL certificate provisioning (30-60 seconds)
- [ ] Press `Ctrl+C` to stop watching logs

### 10. Verify Deployment
- [ ] Check service status: `docker compose -f docker-compose.prod.yml ps`
  - [ ] All services show "running"
  - [ ] postgres shows "healthy"
  - [ ] backend shows "healthy"
- [ ] Test HTTPS redirect: `curl -I http://yourdomain.com`
- [ ] Test HTTPS: `curl -I https://yourdomain.com`
- [ ] Test API health: `curl https://yourdomain.com/api/health`
  - [ ] Should return: `{"status":"healthy"}`
- [ ] Open browser: `https://yourdomain.com`
  - [ ] Frontend loads without errors
  - [ ] Check browser console (should be clean)
  - [ ] Sign-up page is visible
  - [ ] Google OAuth button is hidden

### 11. Test Authentication Flow
- [ ] Create test account via sign-up form
- [ ] Verify account creation succeeds
- [ ] Sign out
- [ ] Sign in with created account
- [ ] Verify redirect to dashboard
- [ ] Check that authenticated API calls work

### 12. Database Verification
- [ ] Check extensions:
  ```bash
  docker compose -f docker-compose.prod.yml exec postgres \
    psql -U ragadmin -d ragadmin -c "\dx"
  ```
  - [ ] `vector` extension is installed
  - [ ] `pg_search` extension is installed
- [ ] Check migrations:
  ```bash
  docker compose -f docker-compose.prod.yml exec backend alembic current
  ```
  - [ ] Shows current migration revision

## Post-Deployment

### 14. Setup Backups
- [ ] Create backup directory: `mkdir -p ~/backups && chmod 700 ~/backups`
- [ ] Test backup manually: `~/rag-admin/backup.sh`
- [ ] Verify backup created: `ls -lh ~/backups/`
- [ ] Setup cron job: `crontab -e`
  - [ ] Add: `0 2 * * * /home/$(whoami)/rag-admin/backup.sh >> /home/$(whoami)/backups/backup.log 2>&1`
- [ ] Save and exit

### 15. Documentation
- [ ] Save `.env.prod` backup in secure location (password manager)
- [ ] Document server IP address
- [ ] Document domain name
- [ ] Document SSH access details
- [ ] Save backup restoration procedure

### 16. Monitoring Setup (Optional)
- [ ] Setup uptime monitoring (UptimeRobot, Healthchecks.io)
- [ ] Configure alerts for downtime
- [ ] Setup log monitoring
- [ ] Configure resource monitoring

## Ongoing Maintenance

### Regular Tasks
- [ ] Check logs weekly: `docker compose -f docker-compose.prod.yml logs --tail=100`
- [ ] Monitor disk space: `df -h`
- [ ] Verify backups are running: `ls -lh ~/backups/`
- [ ] Update system packages monthly: `apt-get update && apt-get upgrade -y`
- [ ] Check SSL certificate auto-renewal is working (automatic via Caddy)

### Application Updates
When updating the application:

**Local machine:**
- [ ] Pull latest changes: `git pull origin main`
- [ ] Rebuild frontend if changed: `cd frontend && npm run build`
- [ ] Transfer frontend to VPS: `scp -r dist user@<VPS_IP>:~/rag-admin/frontend/`

**On VPS:**
- [ ] SSH into VPS
- [ ] Navigate to app directory: `cd ~/rag-admin`
- [ ] Pull backend changes: `git pull origin main`
- [ ] Rebuild backend: `docker compose -f docker-compose.prod.yml build backend`
- [ ] Restart services: `docker compose -f docker-compose.prod.yml up -d --no-deps backend`
- [ ] Restart Caddy: `docker compose -f docker-compose.prod.yml restart caddy`
- [ ] Verify update: `docker compose -f docker-compose.prod.yml ps`
- [ ] Check logs: `docker compose -f docker-compose.prod.yml logs -f backend`

## Troubleshooting

If something goes wrong:

1. **Check service status**: `docker compose -f docker-compose.prod.yml ps`
2. **Check logs**: `docker compose -f docker-compose.prod.yml logs [service-name]`
3. **Restart service**: `docker compose -f docker-compose.prod.yml restart [service-name]`
4. **Review troubleshooting guide**: See `DEPLOYMENT.md` troubleshooting section

## Success Criteria

Your deployment is successful when:
- ✅ All 3 services (postgres, backend, caddy) show "running" status
- ✅ Postgres and backend show "healthy" status
- ✅ HTTPS works without certificate errors
- ✅ API health endpoint returns `{"status":"healthy"}`
- ✅ Frontend loads in browser without errors
- ✅ Can create an account and sign in
- ✅ Database extensions are installed
- ✅ Backups are configured and working
- ✅ Logs show no errors

## Next Steps

After successful deployment:

1. **Enable Google OAuth** (optional)
   - Configure Google OAuth Console
   - Update `.env.prod` with OAuth credentials
   - Uncomment OAuth buttons in frontend
   - Rebuild and restart services

2. **Performance Optimization**
   - Monitor resource usage
   - Optimize database queries
   - Configure CDN for static assets
   - Implement caching strategy

3. **Security Hardening**
   - Review security headers
   - Enable rate limiting
   - Setup fail2ban
   - Regular security audits

4. **Monitoring**
   - Setup log aggregation
   - Configure metrics collection
   - Implement alerting
   - Create dashboards

---

**Need Help?**
- Review `DEPLOYMENT.md` for detailed instructions
- Check `DOCKER.md` for Docker architecture details
- Review service logs for error messages
- Verify all configuration files are correct
