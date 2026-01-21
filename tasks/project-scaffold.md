# Claude Code Task: Project Scaffold

## Objective

Set up the initial project structure for RAG Admin, a web application for managing RAG pipelines. Create the directory structure, configuration files, and boilerplate code. Do not implement any features yet.

## Reference

Read `CLAUDE.md` in the project root for architecture decisions and conventions.

## Tasks

### 1. Create Directory Structure

Create the following directories:

```
rag-admin/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── dependencies/
│   │   └── utils/
│   ├── tests/
│   │   ├── routers/
│   │   ├── services/
│   │   └── repositories/
│   └── alembic/
│       └── versions/
├── frontend/
│   └── src/
│       ├── api/
│       ├── contexts/
│       ├── hooks/
│       ├── pages/
│       ├── components/
│       └── types/
└── scripts/
```

### 2. Backend Setup

#### requirements.txt
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
authlib>=1.3.0
httpx>=0.26.0
slowapi>=0.1.9
python-multipart>=0.0.6
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
```

#### app/config.py
Create settings class using pydantic-settings:
- DATABASE_URL
- JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
- FRONTEND_URL, ALLOWED_ORIGINS, DEBUG

Include a `.env.example` file with placeholder values.

#### app/database.py
Set up async SQLAlchemy:
- Create async engine from DATABASE_URL
- Create async sessionmaker
- Create Base class for models
- Create `get_db` dependency that yields sessions

#### app/main.py
Create FastAPI application with:
- CORS middleware (configured from settings)
- API router with `/api/v1` prefix
- Health check endpoint at `/health`
- Root endpoint returning `{"app": "RAG Admin", "version": "0.1.0"}`

#### alembic.ini and alembic/env.py
Configure Alembic for async SQLAlchemy:
- Read DATABASE_URL from environment
- Import Base from app.database
- Import all models (will be empty initially)
- Configure for async operations

#### tests/conftest.py
Set up pytest fixtures:
- Async test client fixture
- Test database session fixture (use SQLite in-memory for tests, or document PostgreSQL test setup)
- Mark all tests as asyncio

#### Package files
Create `__init__.py` files in all Python packages (can be empty).

### 3. Frontend Setup

#### package.json
Initialize with:
- react, react-dom (^18)
- react-router-dom (^6)
- axios
- typescript
- vite
- @types/react, @types/react-dom
- eslint, prettier (dev dependencies)

#### vite.config.ts
Configure:
- React plugin
- Proxy `/api` to `http://localhost:8000` for development
- Resolve alias `@` to `./src`

#### tsconfig.json
Standard React TypeScript config with:
- Strict mode
- Path alias for `@/*` → `src/*`

#### src/main.tsx
Standard React entry point rendering App into root.

#### src/App.tsx
Basic app shell with:
- BrowserRouter
- Placeholder routes for `/`, `/signin`, `/signup`
- Simple layout wrapper

#### src/api/client.ts
Axios instance with:
- Base URL from environment or default to `/api/v1`
- Request interceptor to add Authorization header from stored token
- Response interceptor for 401 handling (will implement refresh logic later)

#### src/types/auth.ts
TypeScript interfaces:
- User (id, email, fullName, authProvider, createdAt)
- AuthResponse (accessToken, tokenType, expiresIn, user)
- SignInRequest (email, password)
- SignUpRequest (email, password, passwordConfirm, fullName?)

### 4. Development Scripts

#### scripts/dev.sh
```bash
#!/bin/bash
# Start both backend and frontend for development
# Run from project root

trap 'kill 0' EXIT

cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
cd frontend && npm run dev &

wait
```

#### scripts/setup.sh
```bash
#!/bin/bash
# Initial project setup
# Run from project root

echo "Setting up backend..."
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
echo "Edit backend/.env with your configuration"

echo ""
echo "Setting up frontend..."
cd ../frontend
npm install

echo ""
echo "Setup complete. Run ./scripts/dev.sh to start development servers."
```

### 5. Git Configuration

#### .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
venv/
.env
*.egg-info/
dist/
build/

# Node
node_modules/
dist/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.coverage
htmlcov/
.pytest_cache/

# OS
.DS_Store
Thumbs.db
```

## Verification

After completing setup, verify:

1. Backend starts without errors:
   ```bash
   cd backend && source venv/bin/activate && uvicorn app.main:app --reload
   ```
   
2. Health check returns 200:
   ```bash
   curl http://localhost:8000/health
   ```

3. Frontend starts without errors:
   ```bash
   cd frontend && npm run dev
   ```

4. Frontend loads in browser at http://localhost:5173

## Do Not

- Implement authentication (that's the next task)
- Create database models beyond the Base class
- Add complex error handling (keep it simple for now)
- Install additional dependencies not listed

## Questions to Ask Before Starting

1. Confirm the Python version available (expecting 3.12)
2. Confirm Node.js version available (expecting 18+)
3. Should I set up Docker Compose for PostgreSQL, or will you manage the database separately?