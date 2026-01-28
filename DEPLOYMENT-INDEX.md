# Deployment Documentation Index

Complete guide to deploying and automating the RAG Admin application.

## 📚 Documentation Overview

### For First-Time Deployment

Start here if this is your first time deploying the application:

1. **[DEPLOYMENT.md](DEPLOYMENT.md)** ⭐ START HERE
   - Complete step-by-step deployment guide
   - VPS setup instructions
   - Manual deployment process
   - Troubleshooting guide
   - Scaling strategies for production

2. **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)**
   - Checkbox-based deployment checklist
   - Follow this while deploying
   - Ensures no steps are missed

### Understanding the Architecture

Read these to understand how everything works:

3. **[DOCKER.md](DOCKER.md)**
   - Docker container architecture (3 services)
   - Service descriptions and configurations
   - Resource requirements
   - Development vs production setup

4. **[ARCHITECTURE_CHANGES.md](ARCHITECTURE_CHANGES.md)**
   - Why we simplified from 4 to 3 containers
   - Benefits and tradeoffs
   - Migration considerations

### Automation & CI/CD

Set up automated deployment after manual deployment works:

5. **[GITHUB-DEPLOY.md](GITHUB-DEPLOY.md)** ⭐ AUTOMATION GUIDE
   - Complete GitHub Actions CI/CD setup
   - 5 ready-to-use workflow files
   - Step-by-step migration from manual to automated
   - Security best practices
   - Advanced deployment strategies

6. **[GITHUB-DEPLOY-QUICKSTART.md](GITHUB-DEPLOY-QUICKSTART.md)**
   - Quick reference for CI/CD setup
   - 5-step process to get started
   - Minimal viable automation

### Security & Maintenance

Important operational guides:

7. **[SECRETS_ROTATION.md](SECRETS_ROTATION.md)**
   - When and how to rotate secrets
   - Impact of secret changes
   - Emergency rotation procedures
   - Best practices for secret management

## 🎯 Quick Navigation

### I want to...

**Deploy for the first time**
→ Read [DEPLOYMENT.md](DEPLOYMENT.md) and follow [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

**Understand the Docker setup**
→ Read [DOCKER.md](DOCKER.md)

**Set up automated deployment**
→ Read [GITHUB-DEPLOY.md](GITHUB-DEPLOY.md) or [GITHUB-DEPLOY-QUICKSTART.md](GITHUB-DEPLOY-QUICKSTART.md) for quick start

**Update my deployment**
→ See [DEPLOYMENT.md § Update Application](DEPLOYMENT.md#update-application)

**Scale my application**
→ See [DEPLOYMENT.md § Scaling for Production](DEPLOYMENT.md#scaling-for-production)

**Rotate my secrets**
→ Read [SECRETS_ROTATION.md](SECRETS_ROTATION.md)

**Troubleshoot issues**
→ See troubleshooting sections in [DEPLOYMENT.md](DEPLOYMENT.md) and [GITHUB-DEPLOY.md](GITHUB-DEPLOY.md)

**Restore from backup**
→ See [DEPLOYMENT.md § Restore from Backup](DEPLOYMENT.md#restore-from-backup)

## 📋 Deployment Checklist Summary

### Phase 1: Manual Deployment (Day 1)

- [ ] Read DEPLOYMENT.md
- [ ] Set up VPS (Ubuntu, Docker, firewall)
- [ ] Configure DNS
- [ ] Build frontend locally
- [ ] Create .env.prod with secrets
- [ ] Deploy with docker-compose.prod.yml
- [ ] Verify deployment works
- [ ] Set up automated backups

**Time**: 2-3 hours
**Result**: Application running on VPS with HTTPS

### Phase 2: CI/CD Setup (Week 2)

- [ ] Read GITHUB-DEPLOY.md
- [ ] Generate SSH key for GitHub Actions
- [ ] Configure GitHub Secrets
- [ ] Create CI workflow (tests only)
- [ ] Test on staging/development
- [ ] Create CD workflow (deployment)
- [ ] Enable environment protection
- [ ] Test automated deployment

**Time**: 4-6 hours
**Result**: Automated deployment on git push

### Phase 3: Production Hardening (Ongoing)

- [ ] Set up monitoring (UptimeRobot, etc.)
- [ ] Configure alerts
- [ ] Enable automated health checks
- [ ] Set up offsite backups
- [ ] Document runbooks
- [ ] Train team on deployment process

**Time**: Ongoing
**Result**: Production-ready deployment

## 🏗️ Architecture at a Glance

### Services (3 Containers)

```
Internet
   ↓
Caddy (port 443)
   ├─→ Static Files (/*)         → React SPA (from frontend/dist)
   └─→ API Requests (/api/*)     → Backend (FastAPI)
                                      ↓
                                  PostgreSQL (ParadeDB)
```

### Key Features

- ✅ **3 containers**: postgres, backend, caddy
- ✅ **Automatic HTTPS**: Let's Encrypt via Caddy
- ✅ **Static frontend**: Built locally, served by Caddy
- ✅ **Database**: PostgreSQL 16 with pgvector + pg_search
- ✅ **Backups**: Automated daily backups (7-day retention)
- ✅ **Health checks**: Automatic container health monitoring

### Resource Requirements

| Service | RAM | CPU |
|---------|-----|-----|
| PostgreSQL | 256-512 MB | 0.5 core |
| Backend | 128-256 MB | 0.5 core |
| Caddy | 32-128 MB | 0.25 core |
| **Total** | **~500-800 MB** | **1-2 cores** |

**Minimum VPS**: $5-10/month (2GB RAM, 1 CPU)

## 🔐 Security Highlights

### Secrets Management

- **Generate once**: Secrets created during initial setup
- **Never regenerate**: Reuse existing secrets on updates
- **Store securely**: Password manager, encrypted backups
- **Rotate carefully**: Only on security events (see SECRETS_ROTATION.md)

### Deployment Security

- **SSH keys**: Separate key for GitHub Actions
- **Environment protection**: Require approval for production
- **No secrets in Git**: .env.prod only on VPS
- **Automatic HTTPS**: SSL certificates via Let's Encrypt
- **Security headers**: HSTS, CSP, X-Frame-Options, etc.

## 🚀 Deployment Workflows

### Manual Deployment (Current)

```bash
# Local machine
cd frontend && npm run build
scp -r dist user@vps:~/rag-admin/frontend/

# VPS
ssh user@vps
cd ~/rag-admin
git pull
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d
```

**Time**: 5-10 minutes
**Manual steps**: 6-8 commands

### Automated Deployment (With CI/CD)

```bash
# Local machine
git add .
git commit -m "feature: add new feature"
git push origin main

# GitHub Actions automatically:
# 1. Runs tests
# 2. Builds frontend
# 3. Deploys to VPS
# 4. Restarts services
# 5. Verifies health checks
```

**Time**: 3-5 minutes
**Manual steps**: 1 command (git push)

## 📊 Monitoring & Maintenance

### Daily Tasks (Automated)

- ✅ Database backups (2 AM)
- ✅ Health checks (9 AM)
- ✅ SSL certificate renewal (automatic)

### Weekly Tasks (Manual)

- Check application logs
- Review error rates
- Monitor disk usage
- Verify backups exist

### Monthly Tasks (Manual)

- Update system packages
- Review security advisories
- Check resource usage trends
- Test backup restoration

## 🛠️ Common Operations

### View Logs

```bash
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs -f backend  # follow
```

### Restart Service

```bash
docker compose -f docker-compose.prod.yml restart backend
```

### Check Service Status

```bash
docker compose -f docker-compose.prod.yml ps
```

### Run Backup Manually

```bash
~/rag-admin/backup.sh
```

### Restore from Backup

```bash
docker compose -f docker-compose.prod.yml stop backend
gunzip -c backup.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U ragadmin -d ragadmin
docker compose -f docker-compose.prod.yml start backend
```

## 📈 Scaling Path

### Current Setup: VPS (< 1k users)

- Single VPS ($5-20/month)
- 3 containers
- Good for development, staging, small production

### Small Scale: CDN + VPS (1k-10k users)

- Add CloudFront/Cloudflare CDN for frontend
- Managed database (AWS RDS, DigitalOcean)
- Cost: ~$50-150/month

### Medium Scale: Load Balanced (10k-50k users)

- Multiple backend instances
- Database read replicas
- Redis caching
- Cost: ~$200-500/month

### Large Scale: Kubernetes (50k+ users)

- Container orchestration
- Auto-scaling
- Multi-region deployment
- Cost: $1,000+/month

See [DEPLOYMENT.md § Scaling for Production](DEPLOYMENT.md#scaling-for-production) for details.

## 🆘 Getting Help

### Troubleshooting Resources

1. **Common Issues**: [DEPLOYMENT.md § Troubleshooting](DEPLOYMENT.md#troubleshooting)
2. **Docker Issues**: [DOCKER.md § Troubleshooting](DOCKER.md#troubleshooting)
3. **CI/CD Issues**: [GITHUB-DEPLOY.md § Troubleshooting](GITHUB-DEPLOY.md#troubleshooting)

### Emergency Contacts

- Check service logs first
- Review recent deployments
- Test health endpoints
- Verify backup availability
- Document issue before reaching out

## 📝 Next Steps

### If you haven't deployed yet:

1. Start with [DEPLOYMENT.md](DEPLOYMENT.md)
2. Use [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) as you go
3. Test thoroughly before production

### If you have manual deployment working:

1. Read [GITHUB-DEPLOY.md](GITHUB-DEPLOY.md)
2. Set up CI workflow (tests) first
3. Add CD workflow (deployment) after testing
4. Start with staging environment

### If you have CI/CD working:

1. Set up monitoring and alerts
2. Document runbooks
3. Plan for scaling (see DEPLOYMENT.md)
4. Review security practices (SECRETS_ROTATION.md)

---

**Questions?** Review the relevant documentation file or check the troubleshooting sections.

**Contributing?** Update this index when adding new deployment documentation.
