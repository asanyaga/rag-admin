# Common Questions & Clarifications

This document answers common questions about the deployment architecture.

## 1. Why are there Nginx files if we use Caddy?

**Short Answer**: Those files are **NOT USED** - they're kept as references only.

### The Confusion

You might see:
- `frontend/Dockerfile.nginx-reference`
- `frontend/nginx.conf.reference`

And wonder: "Why Nginx if we use Caddy?"

### The Reality

**We simplified the architecture:**

**Before**: 4 containers
- postgres
- backend
- **frontend (Nginx container)** ← Had its own container
- caddy

**After**: 3 containers
- postgres
- backend
- caddy ← Serves static files directly

### The Frontend Now

The frontend is **NOT containerized**:

1. Build locally: `npm run build` → creates `frontend/dist/`
2. Transfer to VPS: `scp -r dist user@vps:~/rag-admin/frontend/`
3. Caddy serves directly from `frontend/dist/`

**No Nginx container!** The Dockerfile and nginx.conf are old files kept for reference.

### Why Keep Them?

In case you want to switch back to a containerized frontend:
- For scaling purposes
- For specific use cases
- To understand the previous architecture

See: `frontend/DOCKER-REFERENCE.md` for details.

## 2. Where is Caddy installed?

**Short Answer**: It's **NOT installed** - it runs in a Docker container.

### The Confusion

You don't see:
- `apt install caddy`
- Caddy installation steps
- Caddy Dockerfile

So where does Caddy come from?

### The Reality

**Caddy uses a pre-built Docker image:**

```yaml
# docker-compose.prod.yml
caddy:
  image: caddy:2-alpine  # ← Downloads from Docker Hub
```

### What Happens

When you run `docker compose up`:

1. Docker checks: "Do I have `caddy:2-alpine` image?"
2. If no: Docker **downloads it from Docker Hub**
3. Docker starts container from image
4. Caddy runs **inside the container**

**No installation on VPS needed!** Caddy is already built into the image.

### Docker Hub

The official Caddy image: https://hub.docker.com/_/caddy

- Maintained by Caddy team
- Pre-built and tested
- ~50MB Alpine-based image
- Includes Caddy server ready to run

See: `caddy/README.md` for detailed explanation.

## 3. How do the containers communicate?

**Containers talk via Docker network:**

```yaml
# docker-compose.prod.yml
networks:
  app-network:
    driver: bridge
```

### Internal Network

Inside the network, containers use service names:

```
postgres:5432    ← Database listens here
backend:8000     ← API listens here
caddy:80         ← Web server (internal)
```

### Example: Backend Connects to Database

```python
# backend/.env.prod
DATABASE_URL=postgresql+asyncpg://ragadmin:password@postgres:5432/ragadmin
#                                              ^^^^^^
#                                        Service name (not IP!)
```

Docker DNS resolves `postgres` → IP of postgres container.

### Example: Caddy Proxies to Backend

```caddyfile
# caddy/Caddyfile
handle /api/* {
    reverse_proxy backend:8000
    #             ^^^^^^^
    #       Service name (not IP!)
}
```

Docker DNS resolves `backend` → IP of backend container.

### External Access

Only **Caddy** is exposed to internet:

```yaml
caddy:
  ports:
    - "80:80"      # HTTP
    - "443:443"    # HTTPS
```

Everything else is **internal only** - no direct access from internet.

## 4. What's actually installed on the VPS?

**Only these programs run directly on VPS:**

1. **Docker** - Container runtime
2. **Docker Compose** - Multi-container orchestration
3. **Git** - For pulling code
4. **Basic OS** - Ubuntu/Debian utilities

**That's it!**

### NOT Installed on VPS

- ❌ Python (runs in backend container)
- ❌ Node.js (used locally for builds)
- ❌ PostgreSQL (runs in postgres container)
- ❌ Caddy (runs in caddy container)
- ❌ Nginx (not used at all)

### Everything Else in Containers

Each container is isolated and has its own:

**postgres container:**
- PostgreSQL 16
- pgvector extension
- pg_search extension
- Its own filesystem
- Its own processes

**backend container:**
- Python 3.12
- FastAPI + dependencies
- Your app code
- Its own filesystem
- Its own processes

**caddy container:**
- Caddy web server
- Your Caddyfile
- Its own filesystem
- Its own processes

See: `DOCKER-IMAGES-EXPLAINED.md` for more details.

## 5. Why build frontend locally instead of in Docker?

**Reasons for local builds:**

### 1. Simplicity
- One less container to manage
- Fewer moving parts
- Easier to understand

### 2. Resource Efficiency
- No frontend container (~32-64MB RAM saved)
- No build process on VPS
- Faster startup time

### 3. Standard Practice
- How most static sites are deployed
- Same as Netlify, Vercel, CloudFront
- Well-established pattern

### 4. Performance
- Caddy is excellent at serving static files
- Direct file serving (no proxy overhead)
- Built-in caching and compression

### When to Use Docker for Frontend

Consider containerizing if:
- You need horizontal scaling (multiple frontend instances)
- Using Kubernetes/orchestration
- Want A/B testing with multiple versions
- Need complex frontend build pipeline

For most cases, static files served by Caddy is better.

## 6. How does HTTPS work with Let's Encrypt?

**Caddy handles everything automatically!**

### What You Do

1. Point DNS to VPS
2. Set domain in Caddyfile:
   ```caddyfile
   yourdomain.com {
       # ...
   }
   ```
3. Run `docker compose up`

### What Caddy Does Automatically

1. **Detects domain** in Caddyfile
2. **Contacts Let's Encrypt** to request certificate
3. **Proves domain ownership** (ACME challenge)
4. **Downloads certificate**
5. **Configures HTTPS**
6. **Redirects HTTP → HTTPS**
7. **Auto-renews** before expiration

**No manual certificate management!** Set and forget.

### Requirements

For automatic HTTPS to work:
- ✅ Domain DNS pointing to VPS
- ✅ Port 80 open (for ACME challenge)
- ✅ Port 443 open (for HTTPS)
- ✅ Valid domain in Caddyfile

### Where Certificates Are Stored

```yaml
volumes:
  caddy_data:  # ← SSL certificates stored here
```

Persists even if container restarts.

## 7. What's the difference between image: and build:?

### image: - Use Pre-built Image

```yaml
caddy:
  image: caddy:2-alpine  # ← Download from Docker Hub
```

**Process:**
1. Docker pulls `caddy:2-alpine` from hub
2. Uses it as-is
3. No building needed

**Use when**: Official images exist (postgres, caddy, redis, nginx, etc.)

### build: - Build Custom Image

```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile  # ← Build from instructions
```

**Process:**
1. Docker reads `backend/Dockerfile`
2. Executes build instructions
3. Creates custom image
4. Uses the built image

**Use when**: Need custom configuration (your application code)

## 8. Why do some files say "NOT USED"?

### Architecture Evolution

We **simplified** the deployment from 4 to 3 containers:

**Removed**: Separate Nginx frontend container
**Kept**: Reference files for documentation

### Files Marked "NOT USED"

- `frontend/Dockerfile.nginx-reference` - Reference only
- `frontend/nginx.conf.reference` - Reference only

These show how to containerize the frontend if you need to scale later.

### Current Production Files

**Actually used in production:**
- ✅ `backend/Dockerfile` - Backend container
- ✅ `backend/entrypoint.sh` - Backend startup
- ✅ `caddy/Caddyfile` - Caddy configuration
- ✅ `docker-compose.prod.yml` - Service orchestration
- ✅ `frontend/dist/` - Static files (served by Caddy)

**Not used (references):**
- 📚 `frontend/Dockerfile.nginx-reference`
- 📚 `frontend/nginx.conf.reference`

## 9. How do I verify my setup?

Run the verification script:

```bash
./verify-setup.sh
```

**Checks for:**
- ✅ All required files present
- ✅ Docker installed
- ✅ Frontend built
- ✅ Configuration correct
- ⚠️ Warnings for placeholders

### Before Deployment

```bash
# Build frontend
cd frontend
npm run build
cd ..

# Verify everything
./verify-setup.sh

# Should show:
# ✓ All checks passed
# ⚠ 2 warnings (expected)
```

## 10. Where can I learn more?

### Quick Reference

- **Setup**: `README.md`
- **Deployment**: `DEPLOYMENT.md`
- **Docker**: `DOCKER.md`
- **CI/CD**: `GITHUB-DEPLOY.md`
- **Navigation**: `DEPLOYMENT-INDEX.md`

### Specific Topics

**Docker Images:**
- `DOCKER-IMAGES-EXPLAINED.md` - How Docker images work
- `caddy/README.md` - Caddy configuration
- `frontend/DOCKER-REFERENCE.md` - Frontend Docker reference

**Deployment:**
- `DEPLOYMENT.md` - Complete deployment guide
- `DEPLOYMENT_CHECKLIST.md` - Step-by-step checklist
- `ARCHITECTURE_CHANGES.md` - Why we simplified

**Automation:**
- `GITHUB-DEPLOY.md` - Complete CI/CD setup
- `GITHUB-DEPLOY-QUICKSTART.md` - Quick start

**Security:**
- `SECRETS_ROTATION.md` - Secret management

### Still Confused?

1. Start with `DEPLOYMENT-INDEX.md` for navigation
2. Read the specific topic documentation
3. Check troubleshooting sections
4. Review this clarifications document

## Summary

### Key Points

1. **Frontend Dockerfile NOT USED** - Kept as reference only
2. **Caddy NOT INSTALLED** - Runs in pre-built Docker container
3. **Only Docker installed on VPS** - Everything else in containers
4. **Build frontend locally** - Transfer static files to VPS
5. **Automatic HTTPS** - Caddy handles Let's Encrypt automatically
6. **3 containers only** - postgres, backend, caddy

### Architecture Diagram

```
VPS (Docker + Docker Compose + Git only)
    ↓
Docker Network (app-network)
    ↓
┌────────────────────────────────────────┐
│                                        │
│  Caddy Container                       │
│  (image: caddy:2-alpine)              │
│  - Serves /srv (frontend/dist)        │
│  - Proxies /api/* to backend          │
│  - Auto HTTPS via Let's Encrypt       │
│                                        │
├────────────────┬───────────────────────┤
│                │                       │
│  Backend       │  PostgreSQL           │
│  (custom)      │  (paradedb image)     │
│  - FastAPI     │  - pgvector           │
│  - Python 3.12 │  - pg_search          │
│                │                       │
└────────────────┴───────────────────────┘

Frontend: Built locally → SCP to VPS → Served by Caddy
Backend: Built in Docker from Dockerfile
Database: Pre-built ParadeDB image
Caddy: Pre-built official Caddy image
```

---

**Still have questions?** Check the related documentation files or create an issue!
