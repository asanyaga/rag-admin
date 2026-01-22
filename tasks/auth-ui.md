# Claude Code Task: Auth UI Implementation

## Objective

Implement the frontend authentication UI: sign-in page, sign-up page, auth context, and a placeholder dashboard. Use shadcn/ui components with a clean, minimalist design.

## Prerequisites

- Project scaffold complete (TASK-01)
- Auth API endpoints working (TASK-03)
- Backend running at `http://localhost:8000`

## Reference Documents

Read these before starting:
- `CLAUDE.md` — Project conventions
- `docs/planning/01-PRD.md` — UI requirements, error messages, password policy
- `docs/planning/03-API-SPEC.md` — API request/response shapes

## Design Direction

- **Component library**: shadcn/ui with default styling
- **Look and feel**: Clean, minimalist, professional
- **Brand colors**: Suggest a simple palette—neutral grays with one accent color. Keep it subtle.
- **Form handling**: Vanilla React (useState)—no form libraries
- **Error handling**: Inline errors under fields for validation, toast notifications for system errors

## Tasks

### 1. Set Up shadcn/ui

Initialize shadcn/ui in the frontend:

```bash
cd frontend
npx shadcn@latest init
```

Install required components:
- Button
- Input
- Label
- Card
- Toast (for notifications)
- Alert (for inline errors)

### 2. API Client

Update `frontend/src/api/client.ts`:

```typescript
// Axios instance with:
// - Base URL: /api/v1 (proxied to backend in dev)
// - Response interceptor: on 401, attempt token refresh
// - Request interceptor: attach access token from memory
```

Create `frontend/src/api/auth.ts`:

```typescript
interface SignUpData {
  email: string;
  password: string;
  passwordConfirm: string;
  fullName?: string;
}

interface SignInData {
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export async function signUp(data: SignUpData): Promise<AuthResponse>
export async function signIn(data: SignInData): Promise<AuthResponse>
export async function signOut(): Promise<void>
export async function refreshToken(): Promise<{ access_token: string }>
export async function getCurrentUser(): Promise<User>
```

### 3. Auth Context

Create `frontend/src/contexts/AuthContext.tsx`:

```typescript
interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (data: SignUpData) => Promise<void>;
  signOut: () => Promise<void>;
}
```

Responsibilities:
- Store access token in memory (not localStorage)
- Store user object in state
- On mount, attempt to refresh token (handles page reload)
- Provide auth state to entire app

Create `frontend/src/hooks/useAuth.ts`:
- Simple hook that consumes AuthContext
- Throws if used outside provider

### 4. Protected Route Component

Create `frontend/src/components/PrivateRoute.tsx`:

- Wrap routes that require authentication
- If not authenticated, redirect to `/signin`
- Show loading state while checking auth

### 5. Password Strength Indicator

Create `frontend/src/components/PasswordStrengthIndicator.tsx`:

Real-time feedback as user types. Check against PRD requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

Display:
- Visual strength bar (red → yellow → green)
- Checklist showing which requirements are met/unmet
- Only show after user starts typing

### 6. Sign Up Page

Create `frontend/src/pages/SignUpPage.tsx`:

**Layout:**
- Centered card on page
- App name/logo at top
- Form fields: email, password, confirm password, full name (optional)
- Password strength indicator below password field
- "Sign up" button
- "Sign up with Google" button (disabled, shows "Coming soon" tooltip)
- Link to sign in page: "Already have an account? Sign in"

**Form State (vanilla React):**
```typescript
const [formData, setFormData] = useState({
  email: '',
  password: '',
  passwordConfirm: '',
  fullName: ''
});
const [errors, setErrors] = useState<Record<string, string>>({});
const [isSubmitting, setIsSubmitting] = useState(false);
```

**Validation:**
- Email format (basic check)
- Password strength (all requirements met)
- Passwords match
- Show inline errors under each field

**On Submit:**
- Validate all fields
- Call auth context signUp
- On success, redirect to dashboard
- On API error, show toast for network errors, inline for field errors

### 7. Sign In Page

Create `frontend/src/pages/SignInPage.tsx`:

**Layout:**
- Centered card on page
- App name/logo at top
- Form fields: email, password
- "Sign in" button
- "Sign in with Google" button (disabled, shows "Coming soon" tooltip)
- Link to sign up page: "Don't have an account? Sign up"

**Form State:**
```typescript
const [formData, setFormData] = useState({
  email: '',
  password: ''
});
const [error, setError] = useState<string | null>(null);
const [isSubmitting, setIsSubmitting] = useState(false);
```

**On Submit:**
- Call auth context signIn
- On success, redirect to dashboard
- On error, show generic "Invalid email or password" (don't reveal which was wrong)

### 8. Dashboard Page (Placeholder)

Create `frontend/src/pages/DashboardPage.tsx`:

Simple placeholder:
- Header with app name and user info
- "Welcome, [user's name or email]!"
- Sign out button
- Message: "RAG Admin dashboard coming soon"

### 9. App Routing

Update `frontend/src/App.tsx`:

```typescript
<AuthProvider>
  <BrowserRouter>
    <Routes>
      <Route path="/signin" element={<SignInPage />} />
      <Route path="/signup" element={<SignUpPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <DashboardPage />
          </PrivateRoute>
        }
      />
    </Routes>
  </BrowserRouter>
  <Toaster /> {/* shadcn toast container */}
</AuthProvider>
```

### 10. Polish

- Loading states on buttons during submission
- Disable form while submitting
- Focus management (autofocus email field)
- Keyboard navigation (Enter to submit)
- Responsive design (works on mobile)

## File Structure

```
frontend/src/
├── api/
│   ├── client.ts          # Axios instance
│   └── auth.ts            # Auth API functions
├── contexts/
│   └── AuthContext.tsx    # Auth state management
├── hooks/
│   └── useAuth.ts         # Auth context consumer
├── components/
│   ├── PrivateRoute.tsx
│   ├── PasswordStrengthIndicator.tsx
│   └── ui/                # shadcn components (auto-generated)
├── pages/
│   ├── SignInPage.tsx
│   ├── SignUpPage.tsx
│   └── DashboardPage.tsx
├── types/
│   └── auth.ts            # TypeScript interfaces
├── App.tsx
└── main.tsx
```

## Verification Checklist

- [ ] shadcn/ui initialized and components installed
- [ ] API client handles token refresh on 401
- [ ] AuthContext manages auth state correctly
- [ ] Sign up form validates all fields inline
- [ ] Password strength indicator shows real-time feedback
- [ ] Sign up creates account and redirects to dashboard
- [ ] Sign in authenticates and redirects to dashboard
- [ ] Sign out clears state and redirects to sign in
- [ ] Protected routes redirect unauthenticated users
- [ ] Page refresh maintains auth state (via token refresh)
- [ ] Google buttons present but disabled
- [ ] Forms are responsive on mobile
- [ ] Manual test: full sign up → sign out → sign in flow works

## Do Not

- Use localStorage for tokens (security risk)
- Implement Google OAuth functionality (TASK-04)
- Add password reset flow (out of scope)
- Use form libraries like react-hook-form (vanilla React for learning)
- Over-engineer state management (no Redux, Zustand, etc.)

## Error Message Reference

From PRD, use these exact messages:

| Scenario | Message |
|----------|---------|
| Invalid email format | "Please enter a valid email address" |
| Email already registered | "An account with this email already exists" |
| Password too weak | Show unmet requirements in strength indicator |
| Passwords don't match | "Passwords do not match" |
| Invalid credentials | "Invalid email or password" |
| Account locked | "Account temporarily locked. Please try again in 15 minutes" |
| Network/server error | "Something went wrong. Please try again" (toast) |

## Notes for Next Task

After this task, TASK-05 will implement:
- Google OAuth button functionality
- OAuth redirect handling
- `/auth/callback` route for OAuth flow