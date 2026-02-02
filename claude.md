# RAG Admin

Web application for creating and managing RAG pipelines. Learning/portfolio project—prioritize clean architecture and readability.

## Stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, PostgreSQL, Alembic
- **Frontend:** React 18, TypeScript, Vite
- **Auth:** JWT + HTTP-only refresh tokens, Google OAuth

## Structure

```
backend/app/    → routers/ → services/ → repositories/ → models/
frontend/src/   → pages/ → components/ → hooks/ → api/
docs/planning/  → PRD, TDD, API spec, database schema
```

## Commands

```bash
# Backend
cd backend && uvicorn app.main:app --reload
cd backend && pytest
cd backend && alembic upgrade head

# Frontend
cd frontend && npm run dev
```

## Patterns

- Data flow: router → service → repository → database
- Services raise exceptions; routers catch and return HTTP responses
- All database operations async
- Type hints on all functions
- Read the relevant spec in `docs/planning/` before implementing features

## UI/Design Direction

### Component Library
- **shadcn/ui** with Tailwind CSS v4 (@tailwindcss/postcss)
- Default slate color scheme with primary blue accent
- Clean, card-based design for forms

### Form Design Pattern
All forms should follow the **shadcn simple login form** pattern with Card and Field components:

**Layout Structure:**
```tsx
<div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
  <div className="w-full max-w-sm">
    <Card>
      <CardHeader>
        <CardTitle>Form Title</CardTitle>
        <CardDescription>Form description text</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <FieldGroup>
            {/* Individual field */}
            <Field>
              <FieldLabel htmlFor="field">Label</FieldLabel>
              <Input id="field" type="text" placeholder="example" required />
              {/* Optional error or help text */}
              <FieldDescription>Helper text</FieldDescription>
            </Field>

            {/* Buttons and footer links go in a Field */}
            <Field>
              <Button type="submit" className="w-full">Submit</Button>
              <Button variant="outline" className="w-full">
                Secondary Action
              </Button>
              <FieldDescription className="text-center">
                Footer text{' '}
                <Link to="/path" className="underline underline-offset-4">
                  Action Link
                </Link>
              </FieldDescription>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  </div>
</div>
```

**Key Principles:**
- Use **Card** wrapper with CardHeader and CardContent
- Full viewport height centering: `min-h-svh` with flex center
- Responsive padding: `p-6 md:p-10`
- Max width constraint: `max-w-sm` on form container
- Use **Field components**: Field, FieldGroup, FieldLabel, FieldDescription
- FieldGroup automatically handles spacing between fields
- Buttons and footer links go inside a Field at the end
- Links: `underline underline-offset-4` for subtle appearance
- All form buttons: full-width (`w-full`)
- Error messages use FieldDescription with `text-destructive` class

**Required Imports:**
```tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
```

**References:**
- Auth forms: `frontend/src/pages/SignInPage.tsx`, `SignUpPage.tsx`
- Reference doc: `docs/planning/shadcn-login-form-block.md`
- Screenshot: `docs/planning/shadcn-simplelogin-block.png`

## Current Focus

Project scaffold → Authentication implementation

## Working with Me

- **Learning preference:** Explain *why* (reasoning, patterns, trade-offs) not basic concepts
- **Session tracking:** Use `/tasks` for work items + `docs/session-log.md` for context
- **Before implementing:** Read relevant PRD in `docs/planning/`, plan first
- **End of session:** Ask for "Session wrap-up" to capture learning and update docs
