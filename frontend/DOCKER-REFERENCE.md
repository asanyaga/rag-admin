# Frontend Docker Reference Files

## ⚠️ Important: These files are NOT used in production

The files in this directory are **reference only** and are **NOT used** in the current deployment:

- `Dockerfile.nginx-reference` - NOT USED (kept for reference)
- `nginx.conf.reference` - NOT USED (kept for reference)

## Current Deployment Architecture

The frontend is **not containerized** in production. Instead:

1. **Build locally**: `npm run build` creates `frontend/dist/`
2. **Transfer to VPS**: `scp -r dist user@vps:~/rag-admin/frontend/`
3. **Caddy serves files**: Static files served directly from `frontend/dist`

See `docker-compose.prod.yml` - there is **no frontend service** defined.

## Why Keep These Files?

These files are kept as references in case you want to:

1. **Switch to containerized frontend** (for scaling)
2. **Use Nginx separately** (for specific use cases)
3. **Understand the previous architecture**

## How Production Actually Works

### docker-compose.prod.yml
```yaml
services:
  postgres: ...    # Database
  backend: ...     # FastAPI (built from backend/Dockerfile)
  caddy:           # Reverse proxy + static file server
    image: caddy:2-alpine  # Pre-built image from Docker Hub
    volumes:
      - ./frontend/dist:/srv:ro  # Mount built frontend
```

**Only 3 containers**: postgres, backend, caddy

### Caddy Configuration (caddy/Caddyfile)
```caddyfile
handle /api/* {
    reverse_proxy backend:8000  # Proxy API to FastAPI
}

handle /* {
    root * /srv                 # Serve static files from /srv
    try_files {path} /index.html
    file_server
}
```

Caddy serves the built React files directly - no Nginx involved!

## If You Want to Use Nginx Container

To switch back to a containerized frontend with Nginx:

1. Rename files back:
   ```bash
   mv Dockerfile.nginx-reference Dockerfile
   mv nginx.conf.reference nginx.conf
   ```

2. Add frontend service to `docker-compose.prod.yml`:
   ```yaml
   frontend:
     build:
       context: ./frontend
       dockerfile: Dockerfile
     container_name: rag-admin-frontend
     restart: unless-stopped
     networks:
       - app-network
   ```

3. Update Caddyfile to proxy to frontend:
   ```caddyfile
   handle /* {
       reverse_proxy frontend:80
   }
   ```

4. Rebuild and deploy:
   ```bash
   docker compose -f docker-compose.prod.yml build frontend
   docker compose -f docker-compose.prod.yml up -d
   ```

See [Architecture Changes](../docs/architecture/README.md) for details on why we simplified.

## Summary

- ❌ `Dockerfile.nginx-reference` - NOT USED in production
- ❌ `nginx.conf.reference` - NOT USED in production
- ✅ `dist/` directory - Used by Caddy to serve static files
- ✅ Build process: `npm run build` → creates `dist/`
- ✅ Deployment: SCP `dist/` to VPS → Caddy serves it

**Current architecture**: 3 containers (postgres + backend + caddy)
**No Nginx container** in production deployment
