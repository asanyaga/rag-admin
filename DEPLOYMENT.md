# RAG Admin - Docker Deployment Guide

This guide provides step-by-step instructions for deploying the RAG Admin application to a production VPS using Docker containers.

## Architecture Overview

The application uses a simplified containerized architecture:

```
Internet → Caddy (443) → [Static Files] Frontend (React SPA)
                       → [/api/*] Backend (8000) [FastAPI] → PostgreSQL (5432) [ParadeDB]
```

### Services (3 containers)

- **PostgreSQL**: ParadeDB latest (PostgreSQL 17 with pgvector and pg_search extensions)
- **Backend**: FastAPI application (Python 3.12) with automatic migrations
- **Caddy**: Reverse proxy with automatic HTTPS via Let's Encrypt + static file server for React SPA

**Note**: The frontend is built locally and served as static files by Caddy. No separate frontend container is needed.

## Prerequisites

- A VPS with at least 2GB RAM and 20GB storage
- Ubuntu 22.04 or later (recommended)
- A registered domain name pointed to your VPS IP
- SSH access to the VPS

## Quick Start

### 1. Prepare Your VPS

SSH into your VPS and install Docker:

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 2. Configure Firewall

```bash
# Install UFW
sudo apt-get install -y ufw

# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable
sudo ufw status
```

### 3. Set Up DNS

Before proceeding, configure your domain's DNS:

- Create an A record pointing `@` (root) to your VPS IP
- Create an A record pointing `www` to your VPS IP
- Wait for DNS propagation (check with `dig +short yourdomain.com`)

### 4. Build Frontend Locally

Before deploying, build the frontend on your local machine:

```bash
# On your local machine
cd /home/asa/rag-admin/frontend

# Install dependencies (if not already done)
npm install

# Build for production
npm run build

# This creates the frontend/dist directory with optimized static files
```

### 5. Transfer Application Code

```bash
# Option A: Clone from Git + copy built frontend
cd ~
git clone <your-repository-url> rag-admin

# Then copy the built frontend from your local machine
# From your local machine:
scp -r /home/asa/rag-admin/frontend/dist user@<VPS_IP>:~/rag-admin/frontend/

# Option B: Transfer entire project via SCP (includes built frontend)
# From your local machine:
scp -r /home/asa/rag-admin user@<VPS_IP>:~/
```

**Important**: Ensure `frontend/dist` directory exists on the VPS before starting Docker services.

### 6. Configure Environment Variables (INITIAL DEPLOYMENT ONLY)

> ⚠️ **CRITICAL**: Secrets should be generated **ONCE** during initial deployment and then **reused forever**.
> Do NOT regenerate secrets on subsequent deployments or all users will be logged out!

Create the production environment file:

```bash
cd ~/rag-admin
cp .env.prod.example .env.prod
```

Generate secure secrets **ONE TIME ONLY**:

```bash
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('SESSION_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
```

Edit `.env.prod` and replace all placeholders:

```bash
nano .env.prod
```

**IMPORTANT**: Replace the following:
- All `CHANGE_THIS_*` passwords with the generated values (copy-paste from above)
- All `yourdomain.com` with your actual domain
- Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set to `disabled`

Secure the file:

```bash
chmod 600 .env.prod
```

**Save your secrets!** Store a copy of `.env.prod` in a secure location:
- Password manager (1Password, Bitwarden, etc.)
- Encrypted backup
- Secure notes

**Why?** If you lose these secrets or regenerate them:
- All users will be logged out (JWT_SECRET_KEY changed)
- All sessions will be invalidated (SESSION_SECRET_KEY changed)
- Database connection will break (POSTGRES_PASSWORD changed)

### 7. Update Caddyfile with Your Domain

Edit the Caddyfile and replace `yourdomain.com` with your actual domain:

```bash
nano caddy/Caddyfile
```

Replace the first line:
```
yourdomain.com {
```

With your actual domain:
```
example.com {
```

### 8. Deploy the Application

Build and start all services:

```bash
cd ~/rag-admin

# Build Docker images
docker compose -f docker-compose.prod.yml build

# Start services in detached mode
docker compose -f docker-compose.prod.yml up -d

# Watch logs to monitor startup
docker compose -f docker-compose.prod.yml logs -f
```

Expected startup sequence:
1. PostgreSQL starts and initializes extensions (10-20 seconds)
2. Backend waits for postgres, runs migrations, starts FastAPI (30-40 seconds)
3. Caddy starts, provisions SSL certificate, and serves static frontend files (30-60 seconds)

Press `Ctrl+C` to stop following logs once everything is running.

### 9. Verify Deployment

Check service status:

```bash
docker compose -f docker-compose.prod.yml ps
```

All services should show "running" status and "healthy" for postgres and backend. You should see 3 containers: postgres, backend, and caddy.

Test the application:

```bash
# Test HTTPS (should work)
curl -I https://yourdomain.com

# Test API health
curl https://yourdomain.com/api/health

# Expected output: {"status":"healthy"}
```

Open your browser and navigate to `https://yourdomain.com`. You should see the sign-up page.

## Post-Deployment Configuration

### Set Up Automated Backups

The `backup.sh` script is included for automated database backups.

Create backup directory:

```bash
mkdir -p ~/backups
chmod 700 ~/backups
```

Test the backup manually:

```bash
~/rag-admin/backup.sh
```

Set up daily automated backups via cron:

```bash
crontab -e
```

Add this line to run backups daily at 2 AM:

```
0 2 * * * /home/$(whoami)/rag-admin/backup.sh >> /home/$(whoami)/backups/backup.log 2>&1
```

### Restore from Backup

To restore a database backup:

```bash
# Stop the backend to prevent connections
docker compose -f docker-compose.prod.yml stop backend

# Restore from backup
gunzip -c ~/backups/ragadmin_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U ragadmin -d ragadmin

# Start the backend
docker compose -f docker-compose.prod.yml start backend
```

## Common Operations

### View Logs

```bash
# View all service logs
docker compose -f docker-compose.prod.yml logs

# View specific service
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs postgres
docker compose -f docker-compose.prod.yml logs caddy

# Follow logs in real-time
docker compose -f docker-compose.prod.yml logs -f backend
```

### Restart Services

```bash
# Restart specific service
docker compose -f docker-compose.prod.yml restart backend

# Restart all services
docker compose -f docker-compose.prod.yml restart
```

### Update Application

When you have new code changes:

```bash
# On your local machine:
cd /home/asa/rag-admin

# Pull latest changes
git pull origin main

# Rebuild frontend (if frontend code changed)
cd frontend
npm install  # if dependencies changed
npm run build

# Transfer updated files to VPS
scp -r dist user@<VPS_IP>:~/rag-admin/frontend/

# On VPS:
cd ~/rag-admin

# Pull backend changes
git pull origin main

# Rebuild backend service
docker compose -f docker-compose.prod.yml build backend

# Restart services (migrations run automatically)
docker compose -f docker-compose.prod.yml up -d --no-deps backend

# Restart Caddy to reload frontend files
docker compose -f docker-compose.prod.yml restart caddy

# Verify update
docker compose -f docker-compose.prod.yml ps
```

> ⚠️ **IMPORTANT**: Do NOT regenerate secrets in `.env.prod` during updates. Reuse the existing file.
> Only modify `.env.prod` if you're changing configuration (e.g., adding OAuth credentials), not secrets.

### Stop and Remove All Services

```bash
# Stop all services
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (WARNING: deletes all data!)
docker compose -f docker-compose.prod.yml down -v
```

## Troubleshooting

### SSL Certificate Not Provisioning

**Symptoms**: HTTP works but HTTPS shows certificate errors

**Solutions**:
1. Verify DNS is pointing to your VPS: `dig +short yourdomain.com`
2. Check firewall allows ports 80 and 443: `sudo ufw status`
3. Check Caddy logs: `docker compose -f docker-compose.prod.yml logs caddy`
4. Ensure domain in Caddyfile matches your actual domain

### Backend Cannot Connect to Database

**Symptoms**: Backend logs show "connection refused" or similar errors

**Solutions**:
1. Check postgres is healthy: `docker compose -f docker-compose.prod.yml ps postgres`
2. Verify DATABASE_URL in .env.prod uses `postgres` as hostname
3. Ensure POSTGRES_PASSWORD matches in DATABASE_URL
4. Check postgres logs: `docker compose -f docker-compose.prod.yml logs postgres`

### Frontend Shows 404 or Blank Page

**Symptoms**: Browser shows blank page or "Cannot GET /"

**Solutions**:
1. Verify `frontend/dist` directory exists on VPS: `ls -la ~/rag-admin/frontend/dist`
2. Check Caddy logs: `docker compose -f docker-compose.prod.yml logs caddy`
3. Rebuild frontend locally and transfer to VPS:
   ```bash
   # Local: cd frontend && npm run build
   # Then: scp -r dist user@<VPS_IP>:~/rag-admin/frontend/
   ```
4. Restart Caddy: `docker compose -f docker-compose.prod.yml restart caddy`

### API Calls Return 502 Bad Gateway

**Symptoms**: Frontend loads but API calls fail

**Solutions**:
1. Check backend is running: `docker compose -f docker-compose.prod.yml ps backend`
2. Check backend logs for errors: `docker compose -f docker-compose.prod.yml logs backend`
3. Test direct backend connection: `docker compose -f docker-compose.prod.yml exec caddy wget -O- http://backend:8000/health`

## Security Best Practices

1. **Keep secrets secure**: Never commit `.env.prod` to version control
2. **Regular updates**: Keep Docker images and system packages updated
3. **Monitor logs**: Regularly check logs for suspicious activity
4. **Backup regularly**: Ensure automated backups are working
5. **Use strong passwords**: Generate strong random passwords for all services
6. **Firewall**: Only expose necessary ports (22, 80, 443)

## Enabling Google OAuth (Optional)

To enable Google OAuth after initial deployment:

1. Configure Google OAuth Console with production redirect URI
2. Update `.env.prod` with production OAuth credentials:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```
3. Uncomment Google OAuth buttons in frontend:
   - `frontend/src/pages/SignUpPage.tsx`
   - `frontend/src/pages/SignInPage.tsx`
4. Rebuild frontend and transfer to VPS:
   ```bash
   # Local: cd frontend && npm run build
   # Transfer: scp -r dist user@<VPS_IP>:~/rag-admin/frontend/
   ```
5. Restart services:
   ```bash
   docker compose -f docker-compose.prod.yml restart backend caddy
   ```

## Monitoring Recommendations

For production deployments, consider:

- **Uptime monitoring**: UptimeRobot, Healthchecks.io
- **Log aggregation**: Grafana Loki, ELK Stack
- **Metrics collection**: Prometheus + Grafana
- **Error tracking**: Sentry
- **Performance monitoring**: Application Performance Monitoring (APM) tools

## Scaling for Production

This deployment is optimized for small to medium workloads (< 1000 concurrent users). For larger scale production deployments, consider these enhancements:

### Frontend Scaling

**Current Setup**: Static files served by Caddy
- **Pros**: Simple, fast for small scale
- **Cons**: Limited scalability, no geographic distribution

**Scaling Options**:

1. **CDN Integration** (Recommended for most cases)
   - Use CloudFront, Cloudflare, or similar CDN
   - Upload `frontend/dist` to S3 or similar storage
   - Configure CDN to cache static assets globally
   - Update Caddyfile to only handle API requests
   - **Benefits**: Global distribution, reduced server load, faster load times
   - **Cost**: ~$5-20/month depending on traffic

2. **Separate Nginx Container** (For containerized scalability)
   - Restore the Nginx container approach
   - Use Docker Swarm or Kubernetes for orchestration
   - Scale frontend containers independently: `docker service scale frontend=5`
   - **Benefits**: Horizontal scaling, better resource management
   - **When**: High traffic (> 10k concurrent users)

3. **Static Site Hosting**
   - Deploy to Vercel, Netlify, or Cloudflare Pages
   - Keep backend on VPS
   - Update CORS settings to allow CDN origin
   - **Benefits**: Automatic CDN, zero frontend server management
   - **Cost**: Free tier available, scales automatically

### Backend Scaling

**Current Setup**: Single FastAPI container
- **Suitable for**: Up to ~1000 concurrent users with proper caching

**Scaling Options**:

1. **Multiple Workers** (First step, minimal cost)
   ```yaml
   backend:
     command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
   - Use workers = (2 × CPU cores) + 1
   - **Benefits**: Better CPU utilization, handle more concurrent requests
   - **Limitations**: Still single container, shared memory

2. **Horizontal Scaling with Load Balancer**
   ```yaml
   backend:
     deploy:
       replicas: 3
   ```
   - Caddy automatically load balances across replicas
   - Requires stateless backend (JWT auth already handles this)
   - **Benefits**: High availability, better fault tolerance
   - **When**: > 5000 concurrent users

3. **Managed Container Service**
   - Deploy to AWS ECS, Google Cloud Run, or Azure Container Instances
   - Auto-scaling based on CPU/memory
   - **Benefits**: Automatic scaling, managed infrastructure
   - **Cost**: ~$50-200/month depending on scale

### Database Scaling

**Current Setup**: Single PostgreSQL container
- **Suitable for**: Up to ~100k rows, moderate query load

**Scaling Options**:

1. **Managed Database Service** (Recommended for production)
   - AWS RDS, Google Cloud SQL, or DigitalOcean Managed Database
   - Automated backups, point-in-time recovery
   - Automated updates and security patches
   - **Benefits**: High availability, automated management
   - **Cost**: ~$15-100/month depending on size
   - **Update**: Change `DATABASE_URL` in `.env.prod` to managed DB endpoint

2. **Connection Pooling** (Low hanging fruit)
   - Add PgBouncer container for connection pooling
   - Reduces database connection overhead
   - **Benefits**: Handle 10x more concurrent connections
   - **Implementation**: Add PgBouncer service to docker-compose

3. **Read Replicas** (For read-heavy workloads)
   - Setup PostgreSQL streaming replication
   - Route read queries to replicas
   - **Benefits**: Distribute read load, improved query performance
   - **When**: > 1 million rows or heavy analytics

4. **Separate Vector Search** (For large RAG workloads)
   - Use dedicated vector database (Pinecone, Weaviate, Qdrant)
   - Keep metadata in PostgreSQL
   - **Benefits**: Optimized vector search, better scaling
   - **When**: > 1 million vector embeddings

### Full Production Architecture

For high-scale production (> 10k concurrent users):

```
                        ┌─────────────────┐
                        │   CloudFront    │ (CDN)
                        │  or Cloudflare  │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼────────┐       ┌───────▼────────┐
            │  Static Files  │       │  API Requests  │
            │   (S3/CDN)     │       │                │
            └────────────────┘       └───────┬────────┘
                                              │
                                     ┌────────▼────────┐
                                     │  Load Balancer  │
                                     │  (ALB/NLB)      │
                                     └────────┬────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     │                        │                        │
            ┌────────▼────────┐      ┌───────▼────────┐      ┌───────▼────────┐
            │   Backend 1     │      │   Backend 2    │      │   Backend 3    │
            │  (Auto-scaled)  │      │ (Auto-scaled)  │      │ (Auto-scaled)  │
            └────────┬────────┘      └───────┬────────┘      └───────┬────────┘
                     │                        │                        │
                     └────────────────────────┼────────────────────────┘
                                              │
                                     ┌────────▼────────┐
                                     │   PgBouncer     │
                                     │  (Connection    │
                                     │   Pooling)      │
                                     └────────┬────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     │                        │                        │
            ┌────────▼────────┐      ┌───────▼────────┐      ┌───────▼────────┐
            │   PostgreSQL    │      │   PostgreSQL   │      │   PostgreSQL   │
            │    Primary      │─────>│   Replica 1    │      │   Replica 2    │
            │  (RDS/Managed)  │      │   (Read-only)  │      │   (Read-only)  │
            └─────────────────┘      └────────────────┘      └────────────────┘
```

### Cost Considerations

**Current Setup (VPS)**: $5-20/month
- Single VPS (DigitalOcean, Linode, etc.)
- Suitable for: Development, staging, small production

**Medium Scale**: $50-150/month
- VPS: $20/month (4GB RAM, 2 CPU)
- Managed Database: $15-50/month
- CDN: $10-30/month
- Suitable for: Small businesses, 1k-10k users

**High Scale**: $200-1000+/month
- Container orchestration: $50-200/month
- Managed database cluster: $100-500/month
- CDN with high traffic: $50-200/month
- Monitoring & observability: $20-100/month
- Suitable for: Enterprise, > 10k concurrent users

### Performance Optimization Checklist

Before scaling infrastructure, optimize the application:

- [ ] Enable database query caching
- [ ] Add Redis for session/result caching
- [ ] Implement database indexes on frequently queried columns
- [ ] Optimize API endpoints (reduce N+1 queries)
- [ ] Enable Gzip/Brotli compression (already enabled in Caddy)
- [ ] Lazy load components in frontend
- [ ] Use database connection pooling
- [ ] Implement rate limiting per user/IP
- [ ] Add query result pagination
- [ ] Optimize vector search queries
- [ ] Use async operations for slow tasks
- [ ] Implement background job processing (Celery, RQ)

### When to Scale

Watch these metrics:

- **CPU > 80%** for extended periods → Add workers or scale horizontally
- **Memory > 85%** consistently → Upgrade instance or scale horizontally
- **Database connections maxed out** → Add connection pooling or read replicas
- **Slow API response times** (> 1s p95) → Optimize queries or scale backend
- **High error rates** (> 1%) → Investigate and fix before scaling

### Migration Path

1. **Start**: Current VPS setup (good for < 1k users)
2. **First upgrade**: Add CDN + managed database (~$50/month, supports 5k users)
3. **Second upgrade**: Multiple backend workers + connection pooling (supports 10k users)
4. **Third upgrade**: Horizontal backend scaling + read replicas (supports 50k+ users)
5. **Enterprise**: Full Kubernetes deployment with auto-scaling

Start simple and scale based on actual usage metrics, not premature optimization.

## Support

For issues and questions:
- Check logs: `docker compose -f docker-compose.prod.yml logs`
- Verify service health: `docker compose -f docker-compose.prod.yml ps`
- Review this troubleshooting guide
- Check Docker and application documentation

## License

[Your License Here]
