# GitHub CI/CD Deployment Guide

This guide explains how to migrate from manual deployment to automated deployment using GitHub Actions.

## Table of Contents

- [Overview](#overview)
- [Benefits of CI/CD](#benefits-of-cicd)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Setup Instructions](#setup-instructions)
- [GitHub Actions Workflows](#github-actions-workflows)
- [Security Best Practices](#security-best-practices)
- [Migration Path](#migration-path)
- [Troubleshooting](#troubleshooting)

## Overview

### Current Manual Process

```
Local Machine:
1. git pull
2. cd frontend && npm run build
3. scp dist/ to VPS
4. SSH to VPS
5. git pull
6. docker compose build
7. docker compose up -d

Time: ~5-10 minutes
Error-prone: Manual steps can be forgotten
```

### Automated CI/CD Process

```
Local Machine:
1. git push to GitHub

GitHub Actions:
2. Run tests automatically
3. Build frontend automatically
4. Deploy to VPS automatically
5. Verify deployment

Time: ~3-5 minutes (hands-free)
Reliable: Same steps every time
```

## Benefits of CI/CD

### Automation
- ✅ Deploy by pushing to main branch
- ✅ Run tests before deployment
- ✅ Build frontend automatically
- ✅ Zero manual steps after push

### Reliability
- ✅ Consistent deployment process
- ✅ No forgotten steps
- ✅ Automatic rollback on failure
- ✅ Deployment logs for debugging

### Quality
- ✅ Tests run before deployment
- ✅ Code linting enforced
- ✅ Build verification
- ✅ Integration tests

### Collaboration
- ✅ Anyone can deploy (with permissions)
- ✅ Audit trail of deployments
- ✅ Staging environments
- ✅ Pull request previews

## Prerequisites

Before setting up CI/CD:

- [ ] Application code in GitHub repository
- [ ] VPS with SSH access
- [ ] Manual deployment working correctly
- [ ] Secrets stored in password manager
- [ ] Basic understanding of GitHub Actions

## Architecture

### CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ GitHub Actions (CI/CD)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Trigger: Push to main                                      │
│     ↓                                                        │
│  1. Checkout code                                           │
│     ↓                                                        │
│  2. Run tests (backend + frontend)                          │
│     ↓                                                        │
│  3. Build frontend (npm run build)                          │
│     ↓                                                        │
│  4. SSH to VPS                                              │
│     ↓                                                        │
│  5. Deploy backend (git pull + docker compose build)        │
│     ↓                                                        │
│  6. Deploy frontend (copy dist/ to VPS)                     │
│     ↓                                                        │
│  7. Restart services                                        │
│     ↓                                                        │
│  8. Verify deployment (health checks)                       │
│     ↓                                                        │
│  ✅ Deployment successful                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Workflow Triggers

- **Push to main**: Automatic deployment to production
- **Pull Request**: Run tests, build check (no deployment)
- **Manual**: Deploy on-demand via workflow_dispatch
- **Scheduled**: Daily health checks

## Setup Instructions

### Step 1: Generate SSH Key for GitHub Actions

On your local machine:

```bash
# Generate SSH key pair for deployment
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy

# This creates:
# - Private key: ~/.ssh/github_actions_deploy
# - Public key: ~/.ssh/github_actions_deploy.pub
```

### Step 2: Add Public Key to VPS

```bash
# Copy public key to clipboard
cat ~/.ssh/github_actions_deploy.pub

# SSH to VPS
ssh user@<VPS_IP>

# Add public key to authorized_keys
echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys

# Verify permissions
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

# Test SSH key works
# From local machine:
ssh -i ~/.ssh/github_actions_deploy user@<VPS_IP>
# Should connect without password
```

### Step 3: Configure GitHub Secrets

Go to your GitHub repository:
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Add the following secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `VPS_HOST` | `your-vps-ip` or `yourdomain.com` | VPS IP address or domain |
| `VPS_USERNAME` | `ragadmin` | SSH username on VPS |
| `VPS_SSH_KEY` | Contents of `~/.ssh/github_actions_deploy` | Private SSH key (entire file) |
| `VPS_PORT` | `22` | SSH port (usually 22) |
| `DEPLOY_PATH` | `/home/ragadmin/rag-admin` | Application path on VPS |

**Optional: For running tests**
| Secret Name | Value | Description |
|-------------|-------|-------------|
| `JWT_SECRET_KEY_TEST` | Any random string | For test environment |
| `SESSION_SECRET_KEY_TEST` | Any random string | For test environment |

**⚠️ IMPORTANT**: Do NOT add production secrets (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`) to GitHub Secrets. These should only exist on the VPS in `.env.prod`.

### Step 4: Create GitHub Actions Workflows

Create `.github/workflows/` directory in your repository:

```bash
mkdir -p .github/workflows
```

We'll create several workflow files (see next section).

### Step 5: Configure Environment Protection (Optional)

For production safety:

1. Go to `Settings` → `Environments`
2. Create environment: `production`
3. Enable "Required reviewers"
4. Add reviewers who must approve deployments
5. Enable "Wait timer" for delayed deployments

## GitHub Actions Workflows

### Workflow 1: CI - Test and Build

**File**: `.github/workflows/ci.yml`

This runs on every push and pull request to verify code quality.

```yaml
name: CI - Test and Build

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test-backend:
    name: Test Backend
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        uses: astral-sh/setup-uv@v2

      - name: Install dependencies
        working-directory: ./backend
        run: |
          uv sync --frozen

      - name: Run tests
        working-directory: ./backend
        env:
          DATABASE_URL: sqlite+aiosqlite:///./test.db
          JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY_TEST }}
          SESSION_SECRET_KEY: ${{ secrets.SESSION_SECRET_KEY_TEST }}
          DEBUG: True
        run: |
          uv run pytest

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./backend/coverage.xml
          fail_ci_if_error: false

  test-frontend:
    name: Test Frontend
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Run linter
        working-directory: ./frontend
        run: npm run lint

      - name: Build frontend
        working-directory: ./frontend
        env:
          VITE_API_URL: /api
        run: npm run build

      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist
          retention-days: 7

  check-docker:
    name: Verify Docker Build
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build backend Docker image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: false
          tags: rag-admin-backend:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Workflow 2: CD - Deploy to Production

**File**: `.github/workflows/deploy-production.yml`

This deploys to production when code is pushed to main.

```yaml
name: CD - Deploy to Production

on:
  push:
    branches: [ main ]
  workflow_dispatch:  # Allow manual trigger

# Ensure only one deployment runs at a time
concurrency:
  group: production-deployment
  cancel-in-progress: false

jobs:
  build-frontend:
    name: Build Frontend
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci --prefer-offline

      - name: Build frontend
        working-directory: ./frontend
        env:
          VITE_API_URL: /api
        run: npm run build

      - name: Upload frontend artifact
        uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist
          retention-days: 1

  deploy:
    name: Deploy to VPS
    needs: build-frontend
    runs-on: ubuntu-latest
    environment: production  # Use if you set up environment protection

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download frontend artifact
        uses: actions/download-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist

      - name: Setup SSH
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.VPS_SSH_KEY }}

      - name: Add VPS to known hosts
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -H ${{ secrets.VPS_HOST }} >> ~/.ssh/known_hosts

      - name: Deploy backend to VPS
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USERNAME: ${{ secrets.VPS_USERNAME }}
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
        run: |
          ssh $VPS_USERNAME@$VPS_HOST << 'EOF'
            set -e
            cd ${{ secrets.DEPLOY_PATH }}

            echo "📦 Pulling latest backend code..."
            git pull origin main

            echo "🐳 Building backend Docker image..."
            docker compose -f docker-compose.prod.yml build backend

            echo "🔄 Restarting backend service..."
            docker compose -f docker-compose.prod.yml up -d --no-deps backend

            echo "✅ Backend deployment complete"
          EOF

      - name: Deploy frontend to VPS
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USERNAME: ${{ secrets.VPS_USERNAME }}
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
        run: |
          # Create temp directory for frontend
          ssh $VPS_USERNAME@$VPS_HOST "mkdir -p ${{ secrets.DEPLOY_PATH }}/frontend/dist.new"

          # Copy built frontend to VPS
          echo "📦 Uploading frontend files..."
          scp -r frontend/dist/* $VPS_USERNAME@$VPS_HOST:${{ secrets.DEPLOY_PATH }}/frontend/dist.new/

          # Atomic swap of frontend directories
          ssh $VPS_USERNAME@$VPS_HOST << 'EOF'
            set -e
            cd ${{ secrets.DEPLOY_PATH }}/frontend

            echo "🔄 Swapping frontend directories..."
            if [ -d "dist.old" ]; then
              rm -rf dist.old
            fi
            if [ -d "dist" ]; then
              mv dist dist.old
            fi
            mv dist.new dist

            echo "🔄 Restarting Caddy..."
            cd ${{ secrets.DEPLOY_PATH }}
            docker compose -f docker-compose.prod.yml restart caddy

            echo "✅ Frontend deployment complete"
          EOF

      - name: Health check
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
        run: |
          echo "🏥 Running health checks..."

          # Wait for services to be ready
          sleep 10

          # Check API health
          if curl -f -s https://$VPS_HOST/api/health > /dev/null; then
            echo "✅ API health check passed"
          else
            echo "❌ API health check failed"
            exit 1
          fi

          # Check frontend
          if curl -f -s https://$VPS_HOST/ > /dev/null; then
            echo "✅ Frontend health check passed"
          else
            echo "❌ Frontend health check failed"
            exit 1
          fi

      - name: Verify deployment
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USERNAME: ${{ secrets.VPS_USERNAME }}
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
        run: |
          ssh $VPS_USERNAME@$VPS_HOST << 'EOF'
            set -e
            cd ${{ secrets.DEPLOY_PATH }}

            echo "📊 Checking service status..."
            docker compose -f docker-compose.prod.yml ps

            echo "📝 Recent logs:"
            docker compose -f docker-compose.prod.yml logs --tail=20 backend
          EOF

      - name: Notify deployment success
        if: success()
        run: |
          echo "🎉 Deployment successful!"
          echo "🔗 Production URL: https://${{ secrets.VPS_HOST }}"

      - name: Rollback on failure
        if: failure()
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USERNAME: ${{ secrets.VPS_USERNAME }}
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
        run: |
          echo "❌ Deployment failed, attempting rollback..."
          ssh $VPS_USERNAME@$VPS_HOST << 'EOF'
            set -e
            cd ${{ secrets.DEPLOY_PATH }}

            # Rollback frontend if old version exists
            if [ -d "frontend/dist.old" ]; then
              echo "Rolling back frontend..."
              rm -rf frontend/dist
              mv frontend/dist.old frontend/dist
              docker compose -f docker-compose.prod.yml restart caddy
            fi

            # Show service status
            docker compose -f docker-compose.prod.yml ps
            docker compose -f docker-compose.prod.yml logs --tail=50 backend
          EOF
```

### Workflow 3: Manual Deployment with Approval

**File**: `.github/workflows/deploy-manual.yml`

For controlled deployments requiring approval.

```yaml
name: Manual Deploy with Approval

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        type: choice
        options:
          - production
          - staging
      skip_tests:
        description: 'Skip tests (not recommended)'
        required: false
        type: boolean
        default: false

jobs:
  run-tests:
    name: Run Tests
    if: ${{ !inputs.skip_tests }}
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install and test backend
        working-directory: ./backend
        run: |
          pip install uv
          uv sync --frozen
          uv run pytest

  request-approval:
    name: Request Approval
    needs: run-tests
    if: ${{ !cancelled() }}
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}

    steps:
      - name: Manual approval checkpoint
        run: |
          echo "🔐 Deployment to ${{ inputs.environment }} approved"
          echo "⏰ Deployment started at: $(date)"

  deploy:
    name: Deploy
    needs: request-approval
    uses: ./.github/workflows/deploy-production.yml
    secrets: inherit
```

### Workflow 4: Scheduled Health Checks

**File**: `.github/workflows/health-check.yml`

Daily automated health checks.

```yaml
name: Scheduled Health Check

on:
  schedule:
    # Run every day at 9 AM UTC
    - cron: '0 9 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  health-check:
    name: Check Production Health
    runs-on: ubuntu-latest

    steps:
      - name: Check API health
        run: |
          if curl -f -s https://${{ secrets.VPS_HOST }}/api/health | grep -q "healthy"; then
            echo "✅ API is healthy"
          else
            echo "❌ API health check failed"
            exit 1
          fi

      - name: Check frontend
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://${{ secrets.VPS_HOST }}/)
          if [ "$STATUS" = "200" ]; then
            echo "✅ Frontend is accessible"
          else
            echo "❌ Frontend returned status: $STATUS"
            exit 1
          fi

      - name: Check SSL certificate
        run: |
          DAYS=$(echo | openssl s_client -servername ${{ secrets.VPS_HOST }} -connect ${{ secrets.VPS_HOST }}:443 2>/dev/null | openssl x509 -noout -dates | grep "notAfter" | cut -d= -f2 | xargs -I {} date -d {} +%s | awk -v now=$(date +%s) '{print int(($1-now)/86400)}')
          echo "SSL certificate expires in $DAYS days"
          if [ "$DAYS" -lt 30 ]; then
            echo "⚠️ SSL certificate expires soon!"
            exit 1
          fi

      - name: Check database connectivity
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USERNAME }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd ${{ secrets.DEPLOY_PATH }}
            docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U ragadmin

      - name: Check disk space
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USERNAME }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
            echo "Disk usage: $USAGE%"
            if [ "$USAGE" -gt 80 ]; then
              echo "⚠️ Disk usage is above 80%!"
              exit 1
            fi

      - name: Send notification on failure
        if: failure()
        run: |
          echo "❌ Health check failed!"
          echo "Check the logs for details"
          # Add notification service here (Slack, Discord, email, etc.)
```

### Workflow 5: Backup Database

**File**: `.github/workflows/backup.yml`

Automated database backups.

```yaml
name: Backup Database

on:
  schedule:
    # Run daily at 3 AM UTC
    - cron: '0 3 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  backup:
    name: Backup PostgreSQL Database
    runs-on: ubuntu-latest

    steps:
      - name: Setup SSH
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.VPS_SSH_KEY }}

      - name: Add VPS to known hosts
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -H ${{ secrets.VPS_HOST }} >> ~/.ssh/known_hosts

      - name: Run backup script
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USERNAME: ${{ secrets.VPS_USERNAME }}
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
        run: |
          ssh $VPS_USERNAME@$VPS_HOST << 'EOF'
            set -e
            cd ${{ secrets.DEPLOY_PATH }}

            echo "📦 Running database backup..."
            ./backup.sh

            echo "📊 Recent backups:"
            ls -lh ~/backups/ | tail -5
          EOF

      - name: Download backup (optional)
        if: github.event_name == 'workflow_dispatch'
        env:
          VPS_HOST: ${{ secrets.VPS_HOST }}
          VPS_USERNAME: ${{ secrets.VPS_USERNAME }}
        run: |
          # Get latest backup filename
          LATEST=$(ssh $VPS_USERNAME@$VPS_HOST "ls -t ~/backups/ragadmin_*.sql.gz | head -1")

          # Download backup
          scp $VPS_USERNAME@$VPS_HOST:$LATEST ./backup.sql.gz

          echo "✅ Backup downloaded: backup.sql.gz"

      - name: Upload backup artifact
        if: github.event_name == 'workflow_dispatch'
        uses: actions/upload-artifact@v4
        with:
          name: database-backup
          path: backup.sql.gz
          retention-days: 30
```

## Security Best Practices

### 1. SSH Key Management

✅ **DO**:
- Use separate SSH keys for GitHub Actions
- Use Ed25519 keys (more secure than RSA)
- Restrict SSH key to specific commands (advanced)
- Rotate SSH keys periodically

❌ **DON'T**:
- Reuse your personal SSH key
- Commit private keys to repository
- Share SSH keys between environments

### 2. Secrets Management

✅ **DO**:
- Store all sensitive data in GitHub Secrets
- Use environment-specific secrets (staging vs production)
- Limit access to secrets (only necessary workflows)
- Audit secret usage regularly

❌ **DON'T**:
- Put secrets in workflow files
- Echo secrets in logs
- Store production secrets in GitHub (keep on VPS only)

### 3. Deployment Safety

✅ **DO**:
- Use environment protection rules
- Require manual approval for production
- Implement health checks after deployment
- Have automatic rollback on failure

❌ **DON'T**:
- Auto-deploy to production without checks
- Skip tests to "save time"
- Deploy without health verification

### 4. Access Control

✅ **DO**:
- Limit who can trigger workflows
- Use environment protection rules
- Enable branch protection on main
- Require pull request reviews

❌ **DON'T**:
- Allow anyone to deploy
- Bypass required status checks
- Merge without review

## Migration Path

### Phase 1: Setup (Week 1)

**Goal**: Get CI working without changing deployment

- [ ] Create GitHub repository (if not already done)
- [ ] Add CI workflow (tests only, no deployment)
- [ ] Configure test secrets
- [ ] Verify tests run on every push
- [ ] Fix any failing tests

**Outcome**: Tests run automatically on every push

### Phase 2: Staging Deployment (Week 2)

**Goal**: Test automated deployment on staging environment

- [ ] Set up staging VPS (or use main VPS with different path)
- [ ] Generate SSH key for GitHub Actions
- [ ] Configure GitHub Secrets
- [ ] Create deployment workflow for staging
- [ ] Test deployment multiple times
- [ ] Verify rollback works

**Outcome**: Confident in automated deployment process

### Phase 3: Production Deployment (Week 3)

**Goal**: Automate production deployment with safety checks

- [ ] Set up environment protection for production
- [ ] Add required approvers
- [ ] Configure production secrets
- [ ] Test deployment workflow on production
- [ ] Set up health check monitoring
- [ ] Document rollback procedures

**Outcome**: Production deploys automatically with approval

### Phase 4: Enhancement (Ongoing)

**Goal**: Improve and optimize CI/CD pipeline

- [ ] Add code coverage reporting
- [ ] Set up deployment notifications (Slack, Discord)
- [ ] Implement preview environments for PRs
- [ ] Add performance testing
- [ ] Schedule automated backups
- [ ] Monitor deployment metrics

**Outcome**: Mature CI/CD pipeline with full automation

## Step-by-Step Migration

### Step 1: Enable GitHub Repository

```bash
# If not already done, push code to GitHub
cd /home/asa/rag-admin
git remote add origin https://github.com/yourusername/rag-admin.git
git branch -M main
git push -u origin main
```

### Step 2: Create Workflow Files

```bash
# Create workflows directory
mkdir -p .github/workflows

# Copy workflow files (see GitHub Actions Workflows section)
# Create each .yml file in .github/workflows/
```

### Step 3: Configure Secrets

1. Go to GitHub repository
2. `Settings` → `Secrets and variables` → `Actions`
3. Add all secrets from [Step 3: Configure GitHub Secrets](#step-3-configure-github-secrets)

### Step 4: Test CI Workflow

```bash
# Make a small change
git checkout -b test-ci
echo "# Testing CI" >> README.md
git add README.md
git commit -m "test: verify CI workflow"
git push origin test-ci

# Create pull request on GitHub
# Verify CI workflow runs and passes
```

### Step 5: Test Deployment (Dry Run)

Modify deployment workflow to add `dry-run` mode:

```yaml
# In deploy-production.yml, add this job first:
  dry-run:
    name: Deployment Dry Run
    runs-on: ubuntu-latest
    steps:
      - name: Show deployment plan
        run: |
          echo "Would deploy to: ${{ secrets.VPS_HOST }}"
          echo "Deploy path: ${{ secrets.DEPLOY_PATH }}"
          echo "Branch: ${{ github.ref_name }}"
```

### Step 6: First Real Deployment

```bash
# Merge test PR to main
# Deployment workflow should trigger automatically

# Monitor deployment:
# Go to GitHub → Actions → Watch the workflow

# Verify deployment succeeded
curl https://yourdomain.com/api/health
```

### Step 7: Set Up Monitoring

Add health check workflow and verify it runs daily.

## Troubleshooting

### SSH Connection Failed

**Error**: `Permission denied (publickey)`

**Solution**:
1. Verify SSH key is correct in GitHub Secrets
2. Check public key is in `~/.ssh/authorized_keys` on VPS
3. Test SSH connection manually:
   ```bash
   ssh -i ~/.ssh/github_actions_deploy user@vps
   ```

### Docker Compose Fails

**Error**: `docker compose command not found`

**Solution**:
1. Check Docker Compose is installed on VPS:
   ```bash
   docker compose version
   ```
2. Update workflow to use `docker-compose` (older syntax) if needed

### Frontend Deployment Failed

**Error**: Frontend not updating after deployment

**Solution**:
1. Check Caddy restarted: `docker compose logs caddy`
2. Verify `frontend/dist` was uploaded
3. Clear browser cache and test

### Health Check Failed

**Error**: Health check returns 502

**Solution**:
1. Check backend logs: `docker compose logs backend`
2. Verify backend is running: `docker compose ps`
3. Check backend health manually: `curl localhost:8000/api/health`

### Deployment Stuck

**Error**: Workflow hangs on deployment step

**Solution**:
1. Check SSH connection isn't waiting for password
2. Verify SSH key has no passphrase
3. Check VPS isn't out of disk space
4. Cancel workflow and redeploy

## Advanced Topics

### Blue-Green Deployment

For zero-downtime deployments:

```yaml
- name: Blue-green deployment
  run: |
    # Deploy to "green" instance
    # Run health checks
    # Switch traffic from "blue" to "green"
    # Keep "blue" as rollback option
```

### Canary Deployment

Gradual rollout to subset of users:

```yaml
- name: Canary deployment
  run: |
    # Deploy to 10% of servers
    # Monitor error rates
    # Gradually increase to 100%
```

### Multi-Environment Setup

Deploy to multiple environments:

```yaml
strategy:
  matrix:
    environment: [staging, production]
```

### Docker Image Registry

Push images to registry instead of building on VPS:

```yaml
- name: Build and push to registry
  uses: docker/build-push-action@v5
  with:
    push: true
    tags: your-registry/rag-admin:${{ github.sha }}
```

### Notifications

Add Slack/Discord notifications:

```yaml
- name: Send deployment notification
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Cost Considerations

### GitHub Actions Free Tier

- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month (free)
- **Storage**: 500 MB (free)

### Typical Usage

- CI workflow (tests): ~5 minutes per run
- Deployment workflow: ~3 minutes per run
- Average: ~10 deployments/day = 80 minutes/day
- Monthly: ~2,400 minutes/month

**Recommendation**: Should fit within free tier for small teams. Upgrade to paid plan (~$4/month for 3,000 additional minutes) if needed.

## Summary

### Benefits Achieved

✅ **Automation**: Deploy with `git push`
✅ **Safety**: Tests run before deployment
✅ **Reliability**: Consistent process every time
✅ **Speed**: 5-10 minutes manual → 3-5 minutes automated
✅ **Audit**: Full deployment history in GitHub
✅ **Rollback**: Automatic on failure
✅ **Collaboration**: Anyone can deploy safely

### Migration Timeline

- **Week 1**: Setup CI (tests)
- **Week 2**: Test on staging
- **Week 3**: Deploy to production
- **Ongoing**: Enhance and optimize

### Next Steps

1. Start with CI workflow (tests only)
2. Test deployment on staging/development
3. Add production deployment with approval
4. Enable monitoring and health checks
5. Iterate and improve based on experience

---

**Ready to start?** Begin with [Phase 1: Setup](#phase-1-setup-week-1) and work through each phase systematically. Don't rush - it's better to test thoroughly at each stage than to automate a broken process!
