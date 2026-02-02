# Migration Summary: Custom Observability → Official SigNoz

**Migration Date:** 2026-02-02
**Status:** ✅ Complete

## Overview

Successfully migrated from custom observability stack (`docker-compose.observability.yml`) to official SigNoz standalone deployment with architecture designed for future portability.

## Changes Made

### 1. New Files Created

- `.github/workflows/deploy-signoz.yml` - Independent SigNoz deployment workflow
- `docker-compose.observability.deprecated.yml` - Renamed from original (kept for reference)
- `MIGRATION_SUMMARY.md` - This file

### 2. Modified Files

#### GitHub Actions Workflows
- **`.github/workflows/deploy.yml`**
  - Added SigNoz availability check before deployment
  - Removed `-f docker-compose.observability.yml` from all commands
  - Backend now connects to external `signoz-net` network

#### Docker Compose Files
- **`docker-compose.prod.yml`**
  - Added `signoz-net` external network definition
  - Connected backend to both `app-network` and `signoz-net`

- **`docker-compose.local.yml`**
  - Added `signoz-net` external network definition
  - Connected backend to both `app-network` and `signoz-net`
  - Updated comments with SigNoz installation instructions

#### Environment Configuration
- **`.env.prod.example`**
  - Updated observability section with clear comments
  - Added examples for same-machine and separate-machine endpoints
  - Documented TLS auto-detection

- **`backend/.env`**
  - Added comments about official SigNoz requirement
  - Clarified endpoint differences for native vs Docker dev

#### Backend Code
- **`backend/app/observability/tracing.py`** (around line 203)
  - Added automatic TLS detection based on endpoint protocol
  - Endpoint starting with `https://` automatically uses secure connection
  - Added debug logging showing TLS status

#### Documentation
- **`docs/observability/README.md`**
  - Complete rewrite with new architecture
  - Sections: Overview, Prerequisites, Local Setup, Production Deployment
  - Added troubleshooting for multi-network setup
  - Added "Future: Moving to Separate Machine" guide

- **`docs/deployment/README.md`**
  - Added SigNoz as optional prerequisite
  - Updated RAM requirement (2GB → 4GB to account for SigNoz)
  - Added link to observability guide

- **`docs/deployment/docker.md`**
  - Added comprehensive "Multi-Network Architecture" section
  - Added network diagram showing app-network and signoz-net
  - Documented backend's dual-network connection
  - Explained service discovery and port exposure

- **`README.md`**
  - Added optional SigNoz installation in Quick Start
  - Added SigNoz UI to access points list
  - Added observability env vars to configuration example

## Architecture Changes

### Before (Custom Stack)

```
docker-compose.prod.yml + docker-compose.observability.yml
├── app-network (single network)
    ├── postgres
    ├── backend
    ├── caddy
    ├── rag-admin-clickhouse
    ├── rag-admin-otel-collector
    └── rag-admin-signoz
```

### After (Official SigNoz)

```
docker-compose.prod.yml (RAG Admin)
├── app-network
    ├── postgres
    ├── backend (also on signoz-net)
    └── caddy

~/signoz/deploy/docker (Official SigNoz)
├── signoz-net (external)
    ├── signoz-otel-collector
    ├── signoz-clickhouse
    ├── signoz-query-service
    └── signoz-zookeeper-1
```

## Benefits

✅ **Portability**: Move SigNoz to different machine by changing only `OTEL_EXPORTER_ENDPOINT`
✅ **Independence**: Deploy SigNoz and RAG Admin separately
✅ **Maintainability**: Official SigNoz gets updates independently
✅ **Future-Ready**: TLS support for internet communication
✅ **Simplicity**: Cleaner architecture with clear separation of concerns
✅ **Cost Optimization**: Easy to move SigNoz to cheaper cloud provider

## Deployment Instructions

### First-Time Setup

1. **Deploy Official SigNoz** (one time):
   ```bash
   ssh user@yourserver.com
   git clone https://github.com/SigNoz/signoz.git ~/signoz
   cd ~/signoz/deploy/docker
   docker compose up -d
   ```

2. **Deploy RAG Admin** (connects automatically):
   ```bash
   cd ~/rag-admin
   git pull origin main
   docker compose -f docker-compose.prod.yml up -d
   ```

3. **Verify Connection**:
   ```bash
   # Check backend is on both networks
   docker inspect rag-admin-backend | jq '.[0].NetworkSettings.Networks | keys'
   # Expected: ["app-network", "signoz-net"]

   # Test connectivity
   docker exec rag-admin-backend curl -v http://signoz-otel-collector:4317
   ```

### GitHub Actions Deployment

1. **Deploy SigNoz** (manual, first time only):
   - Go to Actions → "Deploy SigNoz"
   - Run workflow with server details

2. **Deploy RAG Admin** (automatic on push to main):
   - Workflow checks for SigNoz availability
   - Warns if not available but continues deployment
   - Backend connects to `signoz-net` if available

## Verification Checklist

After deployment, verify:

- [ ] SigNoz is running: `cd ~/signoz/deploy/docker && docker compose ps`
- [ ] signoz-net network exists: `docker network inspect signoz-net`
- [ ] RAG Admin is running: `docker compose -f docker-compose.prod.yml ps`
- [ ] Backend on both networks: `docker inspect rag-admin-backend | grep Networks`
- [ ] Backend can reach collector: `docker exec rag-admin-backend curl http://signoz-otel-collector:4317`
- [ ] Traces appear in SigNoz UI: Visit http://localhost:8080 (via SSH tunnel)

## Rollback Plan

If issues arise, rollback to custom stack:

```bash
cd ~/rag-admin
git revert <migration-commit>
docker compose -f docker-compose.prod.yml -f docker-compose.observability.deprecated.yml down
docker compose -f docker-compose.prod.yml -f docker-compose.observability.deprecated.yml up -d
```

## Cleanup (Optional)

To remove old custom observability volumes:

```bash
# Only run if you're sure you don't need the old data
docker volume rm rag-admin-clickhouse-data rag-admin-signoz-data
```

## Future Migration: Separate Machine

When ready to move SigNoz to a cheaper cloud provider:

1. Deploy SigNoz to new server
2. Expose collector via Caddy or VPN
3. Update `.env.prod`: `OTEL_EXPORTER_ENDPOINT=https://signoz.yourdomain.com:4317`
4. Redeploy backend

**No code changes required!** Backend automatically enables TLS for `https://` endpoints.

## Documentation

All documentation has been updated:

- [Observability Guide](docs/observability/README.md) - Complete setup instructions
- [Deployment Guide](docs/deployment/README.md) - Prerequisites and quick start
- [Docker Configuration](docs/deployment/docker.md) - Multi-network architecture
- [README.md](README.md) - Quick start with optional SigNoz

## Testing

To test locally:

```bash
# 1. Install SigNoz
cd ~/signoz/deploy/docker
docker compose up -d

# 2. Start RAG Admin
cd ~/rag-admin
docker compose -f docker-compose.local.yml up -d

# 3. Generate traffic
curl http://localhost:8000/health

# 4. Check SigNoz UI
open http://localhost:8080
```

## Support

For issues or questions:

- **SigNoz Issues**: https://github.com/SigNoz/signoz/issues
- **RAG Admin Issues**: Check docs/observability/README.md troubleshooting section
- **Network Issues**: See docs/deployment/docker.md multi-network architecture section
