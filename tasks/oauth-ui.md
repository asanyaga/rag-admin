# Claude Code Task: Google OAuth Frontend Implementation

## Objective

Enable Google OAuth on the frontend: handle OAuth callback, extract tokens, enable Google sign-in/sign-up buttons, and handle error states.

## Prerequisites

- Auth UI complete (TASK-04)
- Google OAuth backend complete (TASK-05)
- Backend running with valid Google OAuth credentials

## Reference Documents

Read these before starting:
- `CLAUDE.md` — Project conventions
- `docs/planning/03-API-SPEC.md` — OAuth callback query parameters
- `docs/planning/01-PRD.md` — Error messages for OAuth failures

## Tasks

### 1. OAuth Callback Page

Create `frontend/src/pages/AuthCallbackPage.tsx`:

This page handles the redirect from the backend after Google OAuth.

```typescript
// URL patterns from backend:
// Success: /auth/callback?success=true
// Error: /auth/callback?error=ERROR_CODE&message=optional_message

function AuthCallbackPage() {
  const navigate = useNavigate();
  const { completeOAuthSignIn } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    
    if (params.get('success') === 'true') {
      // Extract access token from cookie, complete sign in
      handleSuccess();
    } else if (params.get('error')) {
      // Show error message
      handleError(params.get('error'), params.get('message'));
    }
  }, []);

  async function handleSuccess() {
    // 1. Read access_token from cookie (set by backend)
    // 2. Call completeOAuthSignIn to store token and fetch user
    // 3. Clear the temporary cookie
    // 4. Redirect to dashboard
  }

  function handleError(code: string, message?: string) {
    // Map error code to user-friendly message
    // Show error state with option to try again
  }

  // Render: loading spinner, or error state
}
```

### 2. Token Extraction Utility

Create `frontend/src/utils/cookies.ts`:

```typescript
export function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? match[2] : null;
}

export function deleteCookie(name: string, path: string = '/'): void {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=${path}`;
}
```

### 3. Update Auth Context

Extend `frontend/src/contexts/AuthContext.tsx`:

Add method to complete OAuth sign-in:

```typescript
interface AuthContextType {
  // ... existing methods ...
  completeOAuthSignIn: () => Promise<void>;
  initiateGoogleSignIn: () => void;
}

function AuthProvider({ children }) {
  // ... existing state ...

  function initiateGoogleSignIn() {
    // Redirect to backend OAuth endpoint
    window.location.href = '/api/v1/auth/google/authorize';
  }

  async function completeOAuthSignIn() {
    // 1. Get access token from cookie
    const accessToken = getCookie('access_token');
    if (!accessToken) {
      throw new Error('No access token found');
    }

    // 2. Store token in memory
    setAccessToken(accessToken);

    // 3. Delete temporary cookie
    deleteCookie('access_token');

    // 4. Fetch current user
    const user = await getCurrentUser();
    setUser(user);
  }

  // ... rest of provider
}
```

### 4. Update Sign In Page

Update `frontend/src/pages/SignInPage.tsx`:

Enable Google button:

```typescript
function SignInPage() {
  const { initiateGoogleSignIn } = useAuth();
  
  // ... existing form state ...

  return (
    // ... existing form ...
    
    <Button
      variant="outline"
      onClick={initiateGoogleSignIn}
      disabled={isSubmitting}
      className="w-full"
    >
      <GoogleIcon className="mr-2 h-4 w-4" />
      Sign in with Google
    </Button>
    
    // ... rest of page
  );
}
```

Remove "Coming soon" tooltip/disabled state from Google button.

### 5. Update Sign Up Page

Update `frontend/src/pages/SignUpPage.tsx`:

Same changes as sign-in page—enable Google button with `initiateGoogleSignIn`.

### 6. Google Icon Component

Create `frontend/src/components/icons/GoogleIcon.tsx`:

```typescript
export function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      {/* Google "G" logo SVG path */}
    </svg>
  );
}
```

Use the official Google "G" logo colors and shape.

### 7. Add Callback Route

Update `frontend/src/App.tsx`:

```typescript
<Routes>
  <Route path="/signin" element={<SignInPage />} />
  <Route path="/signup" element={<SignUpPage />} />
  <Route path="/auth/callback" element={<AuthCallbackPage />} />
  <Route
    path="/"
    element={
      <PrivateRoute>
        <DashboardPage />
      </PrivateRoute>
    }
  />
</Routes>
```

### 8. Error Handling

Map backend error codes to user messages in `AuthCallbackPage`:

```typescript
function getErrorMessage(code: string): string {
  switch (code) {
    case 'OAUTH_FAILED':
      return 'Sign in with Google failed. Please try again.';
    case 'INVALID_STATE':
      return 'Something went wrong. Please try again.';
    case 'EMAIL_EXISTS_DIFFERENT_PROVIDER':
      return 'This email is already registered. Please sign in with your email and password.';
    default:
      return 'Something went wrong. Please try again.';
  }
}
```

Display error with:
- Clear error message
- Button to go back to sign-in page
- Optional "Try again" button

### 9. Loading States

The callback page needs clear loading feedback:

```typescript
function AuthCallbackPage() {
  const [status, setStatus] = useState<'loading' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  // ... handle success/error logic

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">Completing sign in...</p>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md p-6 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive" />
          <h2 className="text-xl font-semibold mb-2">Sign in failed</h2>
          <p className="text-muted-foreground mb-6">{errorMessage}</p>
          <Button onClick={() => navigate('/signin')}>
            Back to sign in
          </Button>
        </Card>
      </div>
    );
  }
}
```

## File Structure

```
frontend/src/
├── pages/
│   ├── AuthCallbackPage.tsx    # New
│   ├── SignInPage.tsx          # Updated
│   └── SignUpPage.tsx          # Updated
├── contexts/
│   └── AuthContext.tsx         # Updated
├── components/
│   └── icons/
│       └── GoogleIcon.tsx      # New
├── utils/
│   └── cookies.ts              # New
└── App.tsx                     # Updated routes
```

## Verification Checklist

- [ ] Google button enabled on sign-in page
- [ ] Google button enabled on sign-up page
- [ ] Clicking Google button redirects to Google consent
- [ ] Successful OAuth redirects to callback page
- [ ] Callback page extracts token and completes sign-in
- [ ] User redirected to dashboard after successful OAuth
- [ ] OAuth errors display user-friendly messages
- [ ] "Email exists" error suggests password sign-in
- [ ] Loading state shows during OAuth completion
- [ ] Temporary access_token cookie is deleted after use
- [ ] Manual test: full Google sign-up flow works
- [ ] Manual test: full Google sign-in flow works (existing user)
- [ ] Manual test: email collision shows correct error

## Do Not

- Store tokens in localStorage
- Implement account linking
- Handle Google token refresh (not needed—we use our own tokens)
- Add Google sign-out (signing out of our app is sufficient)

## Testing Notes

Testing OAuth flows requires real Google credentials and a real browser. For manual testing:

1. Start backend with valid Google OAuth credentials
2. Start frontend
3. Click "Sign in with Google"
4. Complete Google consent
5. Verify redirect back to app and successful sign-in

For automated tests, mock `window.location` for redirect tests and mock the cookie utilities.

## Error Scenarios to Test

| Scenario | How to Trigger | Expected Result |
|----------|----------------|-----------------|
| User cancels consent | Click "Cancel" on Google screen | Error page with retry option |
| Email collision | Use Google account with email already registered via password | Error explaining to use password |
| Network failure | Disconnect during OAuth | Error page with retry option |
| Invalid state | Manually tamper with callback URL | Error page |