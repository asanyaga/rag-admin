# Docker Images Explained

## How Docker Images Work in This Project

If you're new to Docker, you might be wondering: "Where are the programs installed?"

**Short answer**: They're NOT installed on your VPS. They run in **pre-built containers** that Docker downloads automatically.

## The Three Services

### 1. PostgreSQL (Database)

**docker-compose.prod.yml:**
```yaml
postgres:
  image: paradedb/paradedb:v0.19.7-pg16
```

**What this means:**
- `image:` tells Docker to use a pre-built image
- `paradedb/paradedb` is the image name on Docker Hub
- Docker **downloads** this image (not installed on VPS)
- PostgreSQL runs **inside the container**

**No installation needed!** Docker handles everything.

### 2. Backend (FastAPI)

**docker-compose.prod.yml:**
```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile
```

**What this means:**
- `build:` tells Docker to build a custom image
- Uses `backend/Dockerfile` as instructions
- Dockerfile downloads Python, installs dependencies
- Everything runs **inside the container**

**Your VPS doesn't need Python installed!** It's all in the container.

### 3. Caddy (Reverse Proxy)

**docker-compose.prod.yml:**
```yaml
caddy:
  image: caddy:2-alpine
```

**What this means:**
- `image:` tells Docker to use a pre-built image
- `caddy:2-alpine` is downloaded from Docker Hub
- Caddy runs **inside the container**

**No Caddy installation on VPS!** It's all containerized.

## Pre-built vs Custom Images

### Pre-built Images (Pull from Docker Hub)

These services use **official images**:

```yaml
postgres:
  image: paradedb/paradedb:v0.19.7-pg16  # ← Pre-built

caddy:
  image: caddy:2-alpine  # ← Pre-built
```

**What happens:**
1. Docker checks if image exists locally
2. If not, Docker **downloads** from Docker Hub
3. Docker starts container from image
4. Service runs (no installation needed!)

**Analogy**: Like downloading an app from App Store - it's already built and ready to run.

### Custom Images (Build from Dockerfile)

The backend uses a **custom image**:

```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile  # ← Build instructions
```

**What happens:**
1. Docker reads `backend/Dockerfile`
2. Docker **builds** the image (installs Python, dependencies)
3. Docker starts container from built image
4. Service runs

**Analogy**: Like building a custom app from source code.

## Where Are Programs "Installed"?

### On the VPS (Host)

These are the **only** programs on your VPS:

- ✅ Docker
- ✅ Docker Compose
- ✅ Git (for pulling code)
- ✅ Basic OS utilities

**That's it!** No Python, no PostgreSQL, no Caddy installed on host.

### Inside Containers

Each container has its own isolated environment:

**postgres container:**
- PostgreSQL 16
- pgvector extension
- pg_search extension
- Alpine Linux

**backend container:**
- Python 3.12
- FastAPI + dependencies
- Your application code
- Debian-based Linux

**caddy container:**
- Caddy web server
- Your Caddyfile config
- Alpine Linux

## How They Communicate

Containers talk to each other via **Docker network**:

```yaml
networks:
  app-network:
    driver: bridge
```

**Inside the network:**
- `postgres:5432` - Database
- `backend:8000` - API
- `caddy:80/443` - Web server

**From internet:**
- Only Caddy is exposed (ports 80/443)
- Backend and postgres are hidden

## Viewing Downloaded Images

After running `docker compose up`, check downloaded images:

```bash
docker images
```

**Example output:**
```
REPOSITORY              TAG           SIZE
rag-admin-backend       latest        450MB   ← Custom built
caddy                   2-alpine      50MB    ← Downloaded
paradedb/paradedb       v0.19.7-pg16  500MB   ← Downloaded
```

## Image Storage

Images are stored on VPS disk:

```bash
# Check Docker disk usage
docker system df
```

**Example:**
```
TYPE            TOTAL     ACTIVE    SIZE
Images          3         3         1GB
Containers      3         3         50MB
Volumes         4         4         500MB
```

## Common Questions

### Q: Do I need to install Python on the VPS?

**A:** No! Python runs inside the `backend` container. The VPS doesn't need Python.

### Q: Do I need to install Caddy?

**A:** No! Caddy runs inside the `caddy` container from the pre-built `caddy:2-alpine` image.

### Q: Do I need to install PostgreSQL?

**A:** No! PostgreSQL runs inside the `postgres` container from the `paradedb/paradedb` image.

### Q: What if I want to update Caddy?

**A:** Change the image version in docker-compose.prod.yml:

```yaml
caddy:
  image: caddy:2.8-alpine  # ← Update version
```

Then run:
```bash
docker compose -f docker-compose.prod.yml pull caddy
docker compose -f docker-compose.prod.yml up -d caddy
```

### Q: Where does Docker download images from?

**A:** Docker Hub (https://hub.docker.com)

- `caddy:2-alpine` → https://hub.docker.com/_/caddy
- `paradedb/paradedb` → https://hub.docker.com/r/paradedb/paradedb

### Q: Can I see what's inside a container?

**A:** Yes! Use `docker exec`:

```bash
# Open shell in caddy container
docker compose -f docker-compose.prod.yml exec caddy sh

# List files
ls -la /srv  # Your frontend files

# Check Caddy version
caddy version

# Exit
exit
```

### Q: Why doesn't the frontend have an image?

**A:** Because we build it locally and Caddy serves the static files. No container needed for static HTML/CSS/JS.

## Image Updates

### Updating Pre-built Images

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Restart with new images
docker compose -f docker-compose.prod.yml up -d
```

### Updating Custom Images

```bash
# Rebuild backend image
docker compose -f docker-compose.prod.yml build backend

# Restart with new image
docker compose -f docker-compose.prod.yml up -d backend
```

## Cleaning Up Old Images

Over time, old images accumulate:

```bash
# List all images (including old ones)
docker images -a

# Remove unused images
docker image prune

# Remove everything unused (be careful!)
docker system prune -a
```

## Summary

### Key Concepts

1. **Images** = Blueprints (like installation files)
2. **Containers** = Running instances (like running programs)
3. **Pre-built images** = Downloaded from Docker Hub
4. **Custom images** = Built from Dockerfile
5. **No installation on VPS** = Everything runs in containers

### In This Project

| Service | Type | Source |
|---------|------|--------|
| postgres | Pre-built | Docker Hub (paradedb) |
| backend | Custom | Built from backend/Dockerfile |
| caddy | Pre-built | Docker Hub (official) |
| frontend | None | Static files (not containerized) |

### What's Installed Where

**On VPS (host):**
- Docker ✅
- Docker Compose ✅
- Git ✅

**In postgres container:**
- PostgreSQL ✅
- pgvector ✅
- pg_search ✅

**In backend container:**
- Python 3.12 ✅
- FastAPI ✅
- Your app code ✅

**In caddy container:**
- Caddy ✅
- Your Caddyfile ✅

**Nowhere (not needed):**
- Nginx ❌ (not used)
- Node.js ❌ (build locally, not on VPS)

### The Magic of Docker

You type one command:
```bash
docker compose -f docker-compose.prod.yml up -d
```

Docker automatically:
1. ✅ Downloads missing images
2. ✅ Builds custom images
3. ✅ Creates network
4. ✅ Starts containers
5. ✅ Connects everything

**No manual installation of PostgreSQL, Python, or Caddy needed!**

That's the power of containerization! 🐳
