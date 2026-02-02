# GitHub CI/CD Quick Start

This is a condensed version of [ci-cd.md](ci-cd.md) for quick reference.

## Workflows Implemented

The following GitHub Actions workflows are ready to use:

| Workflow | File | Trigger |
|----------|------|---------|
| Backend CI | `.github/workflows/ci-backend.yml` | Push/PR to main (backend changes) |
| Frontend CI | `.github/workflows/ci-frontend.yml` | Push/PR to main (frontend changes) |
| Deploy | `.github/workflows/deploy.yml` | Push to main (after CI passes) |
| Backup | `.github/workflows/backup.yml` | Daily at 2am UTC / Manual |

## Prerequisites

- [ ] Code in GitHub repository
- [ ] VPS with SSH access
- [ ] Manual deployment working

## 5-Step Setup

### 1. Generate SSH Key

```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_deploy
```

### 2. Add Public Key to VPS

```bash
cat ~/.ssh/github_actions_deploy.pub
# Copy output

ssh user@vps
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
```

### 3. Configure GitHub Secrets

Go to: `GitHub Repo` → `Settings` → `Secrets and variables` → `Actions`

**Required secrets:**

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `SSH_HOST` | your-vps-ip or domain | VPS address |
| `SSH_USER` | ragadmin | SSH username |
| `SSH_PRIVATE_KEY` | Contents of `~/.ssh/github_actions_deploy` | Full private key |
| `SSH_PORT` | 22 | SSH port (optional, defaults to 22) |

### 4. Create GitHub Environment

Go to: `GitHub Repo` → `Settings` → `Environments` → `New environment`

1. Create environment named `production`
2. (Optional) Add required reviewers for deployment approval
3. (Optional) Add wait timer for delayed deployments

### 5. Test Deployment

```bash
git add .
git commit -m "Add CI/CD workflows"
git push origin main

# Watch deployment at: GitHub → Actions
```

## What Each Workflow Does

### Backend CI (`ci-backend.yml`)
- Runs on backend file changes
- Sets up Python 3.12 + uv
- Spins up PostgreSQL service container
- Runs pytest with coverage

### Frontend CI (`ci-frontend.yml`)
- Runs on frontend file changes
- Sets up Node.js 20
- Installs dependencies with `npm ci`
- Runs ESLint
- Builds with TypeScript + Vite
- Uploads build artifacts

### Deploy (`deploy.yml`)
- Triggers after push to main
- Waits for CI workflows to pass
- SSH into VPS
- Pulls latest code
- Builds frontend
- Rebuilds Docker containers
- Verifies health checks

### Backup (`backup.yml`)
- Runs daily at 2am UTC
- Can be triggered manually
- Runs existing `backup.sh` script
- Manages backup retention

## Troubleshooting

### SSH Connection Failed

```bash
# Test SSH key locally
ssh -i ~/.ssh/github_actions_deploy user@vps
```

### Deployment Hangs

- Check VPS disk space: `df -h`
- Check Docker is running: `docker ps`
- Check logs: `docker compose logs`

### Health Check Failed

```bash
# On VPS
cd ~/rag-admin
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend
```

### CI Fails on Backend Tests

- Check if PostgreSQL service is healthy
- Verify environment variables are set
- Check test database connection string

## Security Checklist

- [ ] SSH key has no passphrase
- [ ] Private key only in GitHub Secrets
- [ ] Public key only on VPS
- [ ] `.env.prod` never in GitHub
- [ ] Secrets never echoed in logs
- [ ] Branch protection enabled on main
- [ ] Production environment has required reviewers (recommended)

## Full Documentation

For complete setup with advanced features:

👉 **[ci-cd.md](ci-cd.md)**
