# Docker Configuration

This document describes the Docker setup for the RAG Admin application.

## Structure

```
rag-admin/
├── backend/
│   ├── Dockerfile              # Multi-stage Python 3.12 build
│   ├── entrypoint.sh          # Startup script (migrations + server)
│   └── .dockerignore          # Exclude unnecessary files
├── frontend/
│   ├── dist/                   # Built static files (created by npm run build)
│   ├── Dockerfile.nginx-reference  # Reference only (NOT USED)
│   ├── nginx.conf.reference   # Reference only (NOT USED)
│   ├── .dockerignore          # Exclude unnecessary files
│   └── DOCKER-REFERENCE.md    # Explains why Dockerfile is not used
├── caddy/
│   ├── Caddyfile              # Reverse proxy + static file server
│   └── README.md              # Explains Caddy Docker image
├── docker/
│   └── init-db.sql            # PostgreSQL initialization script
├── docker-compose.prod.yml     # Production orchestration (3 services)
├── .env.prod.example          # Production environment template
└── backup.sh                  # Database backup script
```

## Services (3 containers)

### PostgreSQL (postgres)
- **Image**: `paradedb/paradedb:v0.19.7-pg16`
- **Port**: 5432 (internal only)
- **Extensions**: pgvector, pg_search
- **Volume**: `postgres_data` for data persistence
- **Healthcheck**: `pg_isready` every 10s

### Backend (backend)
- **Build**: `./backend/Dockerfile`
- **Port**: 8000 (internal only)
- **Depends on**: postgres (healthy)
- **Environment**: Loaded from `.env.prod`
- **Startup**: Waits for postgres → runs migrations → starts FastAPI
- **Healthcheck**: HTTP GET `/api/health` every 30s

### Caddy (caddy)
- **Image**: `caddy:2-alpine`
- **Ports**: 80, 443, 443/udp (HTTP/3)
- **Features**:
  - Automatic HTTPS via Let's Encrypt
  - Static file server for React SPA
  - Reverse proxy for API
- **Routes**:
  - `/api/*` → reverse proxy to `backend:8000`
  - `/*` → serves static files from `/srv` (mounted from `frontend/dist`)
- **Volumes**:
  - `./frontend/dist:/srv:ro`: Static frontend files
  - `caddy_data`: SSL certificates
  - `caddy_config`: Caddy config cache
  - `caddy_logs`: Access/error logs

## Networking

### Multi-Network Architecture

RAG Admin uses two Docker networks for separation of concerns:

#### 1. app-network (Internal Application Network)
- **Purpose**: Application components communicate with each other
- **Services**: PostgreSQL, Backend, Caddy
- **Type**: Bridge network (managed by RAG Admin)
- **Isolation**: Internal services isolated from direct external access

```yaml
networks:
  app-network:
    driver: bridge
```

#### 2. signoz-net (External Observability Network)
- **Purpose**: Backend sends telemetry to SigNoz observability stack
- **Services**: SigNoz OTel Collector, ClickHouse, Query Service, Zookeeper
- **Type**: External network (managed by official SigNoz deployment)
- **Connection**: Backend container connects to both networks

```yaml
networks:
  signoz-net:
    external: true
    name: signoz-net
```

### Backend Multi-Network Configuration

The backend container is unique—it connects to **both networks**:

```yaml
backend:
  networks:
    - app-network    # To communicate with PostgreSQL
    - signoz-net     # To send telemetry to SigNoz
```

This design allows:
- **Independent deployment**: Deploy SigNoz and RAG Admin separately
- **Easy migration**: Move SigNoz to different machine by changing only `OTEL_EXPORTER_ENDPOINT`
- **Clear separation**: Observability infrastructure is independent from application
- **Optional observability**: RAG Admin works with or without SigNoz

### Network Communication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        app-network                          │
│                                                             │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │ Caddy    │──────│ Backend  │──────│ Postgres │        │
│  └──────────┘      └──────────┘      └──────────┘        │
│       │                   │                                │
└───────│───────────────────│────────────────────────────────┘
        │                   │
        │                   │ Telemetry (OTLP/gRPC)
    Internet            ┌───┴───────────────────────────────┐
        │               │       signoz-net                  │
        ↓               │                                   │
     Users              │  ┌────────────────────────────┐  │
                        │  │ SigNoz OTel Collector      │  │
                        │  │ (port 4317)                │  │
                        │  └────────────────────────────┘  │
                        │                                   │
                        │  ┌────────────────────────────┐  │
                        │  │ ClickHouse                  │  │
                        │  │ (telemetry storage)         │  │
                        │  └────────────────────────────┘  │
                        │                                   │
                        │  ┌────────────────────────────┐  │
                        │  │ SigNoz Query Service        │  │
                        │  │ (UI on port 8080)           │  │
                        │  └────────────────────────────┘  │
                        └───────────────────────────────────┘
```

### Service Discovery

Services use Docker DNS for discovery:

**Within app-network:**
- `postgres` → Resolves to PostgreSQL container
- `backend` → Resolves to Backend container

**Within signoz-net:**
- `signoz-otel-collector` → Resolves to OTel Collector container
- `signoz-clickhouse` → Resolves to ClickHouse container

### Port Exposure

Only Caddy exposes ports to the host:
- **80** (HTTP) → Redirects to HTTPS
- **443** (HTTPS) → Application + API
- **443/udp** (HTTP/3) → Faster connections

All other services are internal:
- PostgreSQL: 5432 (internal only)
- Backend: 8000 (internal only)
- SigNoz Collector: 4317 (internal only)
- SigNoz UI: 8080 (access via SSH tunnel)

## Frontend Build Process

The frontend is **not containerized** in production. Instead:

1. **Build locally** or in CI/CD:
   ```bash
   cd frontend
   npm install
   npm run build  # Creates frontend/dist directory
   ```

2. **Transfer to VPS**:
   ```bash
   scp -r frontend/dist user@<VPS_IP>:~/rag-admin/frontend/
   ```

3. **Caddy serves** the static files directly from `frontend/dist`

This approach:
- Reduces container count (3 instead of 4)
- Lower resource usage
- Simpler deployment
- Faster startup time
- Standard practice for static sites

## Volumes

- **postgres_data**: PostgreSQL database files
- **caddy_data**: SSL certificates and ACME data
- **caddy_config**: Caddy runtime configuration
- **caddy_logs**: Caddy access and error logs

All volumes are persistent and survive container restarts.

## Environment Variables

The backend requires these environment variables (defined in `.env.prod`):

### Database
- `DATABASE_URL`: PostgreSQL connection string (use `postgres` as hostname)
- `POSTGRES_PASSWORD`: PostgreSQL password

### Authentication
- `JWT_SECRET_KEY`: Secret for JWT token signing (64+ chars)
- `JWT_ALGORITHM`: JWT algorithm (HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token TTL
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token TTL
- `SESSION_SECRET_KEY`: Session cookie signing key (64+ chars)

### OAuth (optional)
- `GOOGLE_CLIENT_ID`: Google OAuth client ID (or "disabled")
- `GOOGLE_CLIENT_SECRET`: Google OAuth secret (or "disabled")
- `GOOGLE_REDIRECT_URI`: OAuth callback URL

### CORS
- `FRONTEND_URL`: Frontend origin URL
- `ALLOWED_ORIGINS`: JSON array of allowed origins

### Application
- `DEBUG`: Enable debug mode (False in production)
- `ENVIRONMENT`: Environment name (production)

## Build Process

### Backend Build
1. **Stage 1 (builder)**: Install dependencies with `uv`
2. **Stage 2 (runtime)**: Copy virtual env, add app code, install postgres-client

### Frontend Build
1. **Stage 1 (builder)**: `npm ci` → `npm run build` with `VITE_API_URL=/api`
2. **Stage 2 (runtime)**: Copy build artifacts to Nginx

## Startup Sequence

1. **PostgreSQL** starts first
   - Runs `init-db.sql` to create extensions
   - Healthcheck waits for `pg_isready`

2. **Backend** waits for postgres healthy
   - `entrypoint.sh` polls `pg_isready`
   - Runs `alembic upgrade head`
   - Starts `uvicorn`

3. **Caddy** starts last
   - Provisions SSL certificate from Let's Encrypt
   - Serves static files from `frontend/dist`
   - Proxies API requests to backend
   - Routes traffic

## Health Checks

Services implement health checks:

- **postgres**: `pg_isready -U ragadmin -d ragadmin` (10s interval)
- **backend**: `wget http://localhost:8000/api/health` (30s interval)

Health checks ensure:
- Services are ready before receiving traffic
- Docker can detect and restart failed containers
- Dependencies wait for upstream services

## Security Features

### Container Security
- Backend runs as non-root user (`appuser`)
- Frontend uses Nginx Alpine (minimal attack surface)
- No privileged containers
- Internal network isolation

### TLS/HTTPS
- Automatic HTTPS via Let's Encrypt
- HTTP to HTTPS redirect
- Certificate auto-renewal
- HTTP/3 support (QUIC)

### HTTP Headers
Caddy adds security headers:
- `Strict-Transport-Security`: Force HTTPS
- `X-Content-Type-Options`: Prevent MIME sniffing
- `X-Frame-Options`: Prevent clickjacking
- `X-XSS-Protection`: Enable XSS filtering
- `Referrer-Policy`: Control referrer information
- `Permissions-Policy`: Restrict browser features

### Nginx Security
- File caching with proper headers
- No directory listing
- SPA fallback routing
- API requests rejected (handled by Caddy)

## Backup Strategy

The `backup.sh` script provides automated backups:

- Creates compressed SQL dumps (`ragadmin_YYYYMMDD_HHMMSS.sql.gz`)
- Stores in `~/backups/`
- Retains backups for 7 days
- Logs to `~/backups/backup.log`
- Can be scheduled via cron

### Backup Restoration

```bash
# Stop backend
docker compose -f docker-compose.prod.yml stop backend

# Restore backup
gunzip -c backup.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U ragadmin -d ragadmin

# Start backend
docker compose -f docker-compose.prod.yml start backend
```

## Resource Requirements

Minimum recommended resources:

- **CPU**: 2 cores
- **RAM**: 2GB
- **Disk**: 20GB SSD
- **Network**: 100 Mbps

Resource usage by service (approximate):

- **postgres**: 256MB-512MB RAM
- **backend**: 128MB-256MB RAM
- **caddy**: 32MB-128MB RAM (serves static files + proxies API)

**Total**: ~500MB-800MB RAM for all services

## Monitoring

### Logs

View logs for all services:
```bash
docker compose -f docker-compose.prod.yml logs -f
```

View specific service:
```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

Caddy logs are also stored in the `caddy_logs` volume:
- `/var/log/caddy/access.log`: Access logs (JSON format)
- `/var/log/caddy/error.log`: Error logs

### Health Monitoring

Check service health:
```bash
docker compose -f docker-compose.prod.yml ps
```

All healthy services show "healthy" status.

## Scaling Considerations

To scale the backend:

1. Remove health check dependency in docker-compose.prod.yml
2. Add multiple backend replicas:
   ```yaml
   backend:
     deploy:
       replicas: 3
   ```
3. Caddy automatically load balances across replicas

For high-traffic production:
- Use external PostgreSQL (e.g., AWS RDS, managed service)
- Add Redis for session caching
- Use CDN for static assets
- Implement database connection pooling
- Add horizontal pod autoscaling

## Development vs Production

This configuration is for **production only**.

For local development:
- Backend: `cd backend && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm run dev`
- Database: Local PostgreSQL or Docker

Don't use `docker-compose.prod.yml` for development as it:
- Uses production builds (no hot reload)
- Requires real domain for SSL
- Includes production optimizations
- Lacks development tools
- Frontend must be built (no live reloading)

## Why Not Containerize the Frontend?

You might wonder why we don't run the frontend in a container. Here's the reasoning:

### Current Approach: Static Files + Caddy
- Simple: Fewer moving parts
- Efficient: No extra container overhead
- Fast: Direct file serving
- Standard: How most SPAs are deployed
- Resource-friendly: Uses ~32-64MB RAM less

### Alternative: Nginx Container
Would add:
- Another container to manage
- ~32-64MB RAM overhead
- Extra complexity
- No real benefit for static files

### When to Use a Frontend Container

Consider using a separate frontend container (Nginx) if:
1. You need to scale frontend independently from backend
2. You're using container orchestration (Kubernetes, Docker Swarm)
3. You want A/B testing with multiple frontend versions
4. You have a complex frontend build pipeline

For most deployments, serving static files from Caddy is the better choice.

---

## FAQ

### Why are there Nginx files if we use Caddy?

**Short Answer**: Those files are **NOT USED** - they're kept as references only.

You might see:
- `frontend/Dockerfile.nginx-reference`
- `frontend/nginx.conf.reference`

We simplified the architecture from 4 containers to 3. The frontend is **NOT containerized**:

1. Build locally: `npm run build` → creates `frontend/dist/`
2. Transfer to VPS: `scp -r dist user@vps:~/rag-admin/frontend/`
3. Caddy serves directly from `frontend/dist/`

**No Nginx container!** The Dockerfile and nginx.conf are kept for reference in case you want to switch back.

### Where is Caddy installed?

**Short Answer**: It's **NOT installed** - it runs in a Docker container.

Caddy uses a pre-built Docker image:

```yaml
# docker-compose.prod.yml
caddy:
  image: caddy:2-alpine  # Downloads from Docker Hub
```

When you run `docker compose up`:
1. Docker checks: "Do I have `caddy:2-alpine` image?"
2. If no: Docker **downloads it from Docker Hub**
3. Docker starts container from image
4. Caddy runs **inside the container**

**No installation on VPS needed!**

### How do the containers communicate?

Containers talk via Docker network:

```yaml
# docker-compose.prod.yml
networks:
  app-network:
    driver: bridge
```

Inside the network, containers use service names:

```
postgres:5432    ← Database listens here
backend:8000     ← API listens here
caddy:80         ← Web server (internal)
```

Docker DNS resolves service names to container IPs automatically.

Only **Caddy** is exposed to the internet:

```yaml
caddy:
  ports:
    - "80:80"      # HTTP
    - "443:443"    # HTTPS
```

Everything else is **internal only**.

### What's actually installed on the VPS?

**Only these programs run directly on VPS:**

1. **Docker** - Container runtime
2. **Docker Compose** - Multi-container orchestration
3. **Git** - For pulling code
4. **Basic OS** - Ubuntu/Debian utilities

**NOT Installed on VPS:**
- Python (runs in backend container)
- Node.js (used locally for builds)
- PostgreSQL (runs in postgres container)
- Caddy (runs in caddy container)
- Nginx (not used at all)

### What's the difference between `image:` and `build:`?

**`image:`** - Use Pre-built Image:
```yaml
caddy:
  image: caddy:2-alpine  # Download from Docker Hub
```
Docker pulls the image and uses it as-is.

**`build:`** - Build Custom Image:
```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile  # Build from instructions
```
Docker reads the Dockerfile and builds a custom image.

### How does HTTPS work with Let's Encrypt?

**Caddy handles everything automatically!**

What you do:
1. Point DNS to VPS
2. Set domain in Caddyfile
3. Run `docker compose up`

What Caddy does automatically:
1. Detects domain in Caddyfile
2. Contacts Let's Encrypt
3. Proves domain ownership (ACME challenge)
4. Downloads certificate
5. Configures HTTPS
6. Redirects HTTP → HTTPS
7. Auto-renews before expiration

**Requirements:**
- Domain DNS pointing to VPS
- Port 80 open (for ACME challenge)
- Port 443 open (for HTTPS)
- Valid domain in Caddyfile

---

## Troubleshooting

### Container won't start
```bash
# View container logs
docker compose -f docker-compose.prod.yml logs [service]

# Inspect container
docker compose -f docker-compose.prod.yml ps -a

# Rebuild without cache
docker compose -f docker-compose.prod.yml build --no-cache [service]
```

### Database connection issues
```bash
# Check postgres is running
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U ragadmin

# Test connection from backend
docker compose -f docker-compose.prod.yml exec backend env | grep DATABASE

# Access postgres shell
docker compose -f docker-compose.prod.yml exec postgres psql -U ragadmin -d ragadmin
```

### SSL certificate issues
```bash
# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy | grep -i certificate

# Verify DNS
dig +short yourdomain.com

# Test HTTP (should redirect to HTTPS)
curl -I http://yourdomain.com
```

### Service communication issues
```bash
# Test backend from caddy
docker compose -f docker-compose.prod.yml exec caddy wget -O- http://backend:8000/health

# Check network
docker network inspect rag-admin_app-network
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Caddy Documentation](https://caddyserver.com/docs/)
- [ParadeDB Documentation](https://docs.paradedb.com/)
