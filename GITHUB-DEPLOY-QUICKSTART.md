# GitHub CI/CD Quick Start

This is a condensed version of [GITHUB-DEPLOY.md](GITHUB-DEPLOY.md) for quick reference.

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

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `VPS_HOST` | your-vps-ip or domain |
| `VPS_USERNAME` | ragadmin |
| `VPS_SSH_KEY` | Contents of `~/.ssh/github_actions_deploy` (private key) |
| `DEPLOY_PATH` | /home/ragadmin/rag-admin |

### 4. Create Workflow File

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Build frontend
        working-directory: ./frontend
        run: |
          npm ci
          npm run build

      - name: Setup SSH
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.VPS_SSH_KEY }}

      - name: Deploy
        env:
          HOST: ${{ secrets.VPS_HOST }}
          USER: ${{ secrets.VPS_USERNAME }}
          PATH: ${{ secrets.DEPLOY_PATH }}
        run: |
          ssh-keyscan -H $HOST >> ~/.ssh/known_hosts

          # Deploy frontend
          scp -r frontend/dist/* $USER@$HOST:$PATH/frontend/dist/

          # Deploy backend
          ssh $USER@$HOST "cd $PATH && git pull && docker compose -f docker-compose.prod.yml build backend && docker compose -f docker-compose.prod.yml up -d --no-deps backend && docker compose -f docker-compose.prod.yml restart caddy"
```

### 5. Test Deployment

```bash
git add .
git commit -m "Add CI/CD workflow"
git push origin main

# Watch deployment at: GitHub → Actions
```

## What This Does

1. ✅ Runs on every push to `main`
2. ✅ Builds frontend automatically
3. ✅ Deploys to VPS via SSH
4. ✅ Restarts services
5. ✅ Takes 3-5 minutes

## Next Steps

- Add tests: See [GITHUB-DEPLOY.md § CI Workflow](GITHUB-DEPLOY.md#workflow-1-ci---test-and-build)
- Add health checks: See [GITHUB-DEPLOY.md § Health Checks](GITHUB-DEPLOY.md#workflow-4-scheduled-health-checks)
- Add manual approval: See [GITHUB-DEPLOY.md § Manual Deployment](GITHUB-DEPLOY.md#workflow-3-manual-deployment-with-approval)
- Add notifications: See [GITHUB-DEPLOY.md § Advanced Topics](GITHUB-DEPLOY.md#notifications)

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

## Full Documentation

For complete setup with tests, health checks, backups, and advanced features:

👉 **[GITHUB-DEPLOY.md](GITHUB-DEPLOY.md)**

## Security Checklist

- [ ] SSH key has no passphrase
- [ ] Private key only in GitHub Secrets
- [ ] Public key only on VPS
- [ ] `.env.prod` never in GitHub
- [ ] Secrets never echoed in logs
- [ ] Branch protection enabled on main
