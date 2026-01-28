# Caddy Configuration

## How Caddy Works in This Deployment

### No Installation Required!

Caddy is **not installed** on the VPS. Instead, we use the official **Caddy Docker image** from Docker Hub.

### In docker-compose.prod.yml

```yaml
caddy:
  image: caddy:2-alpine  # ← Docker pulls this image automatically
  container_name: rag-admin-caddy
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    - ./frontend/dist:/srv:ro
```

### What Happens When You Run `docker compose up`

1. **Docker checks** if `caddy:2-alpine` image exists locally
2. **If not**, Docker automatically **pulls it from Docker Hub**
3. **Docker starts** the container with your `Caddyfile` configuration
4. **Caddy runs** inside the container (no installation on host)

### The Official Caddy Image

- **Image**: `caddy:2-alpine`
- **Source**: https://hub.docker.com/_/caddy
- **Base**: Alpine Linux (minimal, ~50MB)
- **Includes**: Caddy server pre-installed and configured
- **Maintained**: Official Caddy team

### How It Gets Your Configuration

The Caddyfile in this directory is **mounted** into the container:

```yaml
volumes:
  - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
```

This means:
- Your local `Caddyfile` → Container's `/etc/caddy/Caddyfile`
- Changes to `Caddyfile` → Restart caddy to apply
- No rebuild needed (just volume mount)

### How It Serves Your Frontend

```yaml
volumes:
  - ./frontend/dist:/srv:ro
```

Your built frontend files are mounted at `/srv` inside the container, and the Caddyfile tells Caddy to serve from there:

```caddyfile
handle /* {
    root * /srv  # Serve files from /srv (your frontend/dist)
    try_files {path} /index.html
    file_server
}
```

## Caddy's Role in Your Architecture

```
Internet (port 443)
        ↓
    Caddy Container
        ↓
    ┌───────────────────┐
    │                   │
/api/*              /*
    │                   │
    ↓                   ↓
Backend:8000    Static Files (/srv)
(FastAPI)       (frontend/dist)
```

### What Caddy Does

1. **Automatic HTTPS**
   - Obtains SSL certificate from Let's Encrypt
   - Auto-renews certificates (no intervention needed)
   - Redirects HTTP → HTTPS

2. **Reverse Proxy**
   - Proxies `/api/*` to backend container
   - Adds security headers
   - Handles compression (gzip/zstd)

3. **Static File Server**
   - Serves frontend files from `/srv`
   - Sets proper cache headers
   - SPA routing (fallback to index.html)

## Configuration Files

### Caddyfile (This Directory)

The only configuration file you need to edit:

```caddyfile
yourdomain.com {
    # Your domain goes here ^^

    # Security headers (automatic)
    # Compression (automatic)
    # SSL/TLS (automatic)

    # API proxy
    handle /api/* {
        reverse_proxy backend:8000
    }

    # Frontend static files
    handle /* {
        root * /srv
        try_files {path} /index.html
        file_server
    }
}
```

### What You Need to Change

Only **one thing**: Replace `yourdomain.com` with your actual domain!

```caddyfile
example.com {  # ← Change this
    # ...
}
```

Everything else is automatic:
- ✅ HTTPS certificate
- ✅ Auto-renewal
- ✅ HTTP → HTTPS redirect
- ✅ Security headers
- ✅ Compression

## Viewing Caddy Logs

Since Caddy runs in a Docker container:

```bash
# View logs
docker compose -f docker-compose.prod.yml logs caddy

# Follow logs in real-time
docker compose -f docker-compose.prod.yml logs -f caddy

# View specific log file
docker compose -f docker-compose.prod.yml exec caddy cat /var/log/caddy/access.log
docker compose -f docker-compose.prod.yml exec caddy cat /var/log/caddy/error.log
```

## Restarting Caddy

After changing the Caddyfile:

```bash
docker compose -f docker-compose.prod.yml restart caddy
```

No rebuild needed! The Caddyfile is mounted as a volume.

## Caddy Data Persistence

Caddy stores data in Docker volumes:

```yaml
volumes:
  caddy_data:    # SSL certificates
  caddy_config:  # Runtime configuration
  caddy_logs:    # Access and error logs
```

These persist even if you stop/remove the container.

## Troubleshooting

### Caddy Won't Start

```bash
# Check if port 80/443 is available
sudo netstat -tlnp | grep -E ':80|:443'

# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy

# Test Caddyfile syntax
docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile
```

### SSL Certificate Issues

```bash
# Check Caddy logs for Let's Encrypt errors
docker compose -f docker-compose.prod.yml logs caddy | grep -i certificate

# Verify DNS is pointing to VPS
dig +short yourdomain.com

# Check firewall allows 80/443
sudo ufw status
```

### Frontend Not Loading

```bash
# Check if dist directory is mounted
docker compose -f docker-compose.prod.yml exec caddy ls -la /srv

# Should show index.html and assets/

# Check Caddy file_server logs
docker compose -f docker-compose.prod.yml logs caddy | grep file_server
```

## Advanced: Customizing Caddy

### Add Custom Headers

Edit Caddyfile:

```caddyfile
yourdomain.com {
    header {
        Custom-Header "My Value"
    }
}
```

### Enable Access Logs

Already enabled in Caddyfile:

```caddyfile
log {
    output file /var/log/caddy/access.log
    format json
}
```

### Add Rate Limiting

```caddyfile
handle /api/* {
    rate_limit {
        zone api {
            key {remote_host}
            events 100
            window 1m
        }
    }
    reverse_proxy backend:8000
}
```

## Comparison: Caddy vs Nginx

| Feature | Caddy | Nginx |
|---------|-------|-------|
| HTTPS Setup | Automatic | Manual (certbot) |
| Certificate Renewal | Automatic | Manual (cron) |
| Configuration | Simple | Complex |
| HTTP/3 | Built-in | Requires compilation |
| Docker Image Size | ~50MB | ~25MB |
| Learning Curve | Easy | Steep |

## Why We Use Caddy

1. **Automatic HTTPS** - Zero configuration needed
2. **Simple config** - Caddyfile is easy to read/write
3. **Modern protocols** - HTTP/2, HTTP/3 out of box
4. **Great for Docker** - Official images, well maintained
5. **Production ready** - Used by many large deployments

## Summary

### Key Points

- ✅ Caddy is **NOT installed** - it runs in a Docker container
- ✅ Docker **automatically pulls** the official `caddy:2-alpine` image
- ✅ Caddyfile is **mounted** from this directory
- ✅ Frontend files are **mounted** from `frontend/dist`
- ✅ SSL certificates are **automatic** (Let's Encrypt)
- ✅ No manual certificate management needed

### Files in This Directory

- `Caddyfile` - Main configuration (edit domain here)
- `README.md` - This file

### No Installation Steps Because:

Docker handles everything:
1. Pulls official Caddy image
2. Mounts your configuration
3. Mounts your frontend files
4. Starts the server
5. Obtains SSL certificates automatically

**That's it!** No `apt install`, no compilation, no manual setup. Just `docker compose up` and Caddy runs.
