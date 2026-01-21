# Claude Code Workflow Guide (Revised)

Based on Anthropic's official best practices and community learnings.

## Core Principles

1. **CLAUDE.md should be concise** — LLMs follow ~150 instructions reliably; Claude Code's system prompt uses ~50. Every line competes for attention.

2. **Use `/clear` frequently** — Context degradation is the primary failure mode. Clear between tasks.

3. **Plan before coding** — Ask Claude to explore and plan first. Explicitly say "don't write code yet."

4. **Use thinking keywords** — "think" < "think hard" < "think harder" < "ultrathink" for progressively deeper reasoning.

5. **Course correct early** — Escape to interrupt, double-Escape to go back and try differently.

## Session Pattern

```
/clear                              ← Start fresh
"Read [files]. Don't code yet."     ← Explore
"Think hard. Make a plan."          ← Plan  
[Review plan, ask questions]        ← Verify
"Implement your plan."              ← Code
"Run tests. Fix any failures."      ← Validate
"Commit with descriptive message."  ← Save
/clear                              ← Reset for next task
```

## Prompting Examples

### Starting a Feature

```
Read docs/planning/03-API-SPEC.md and the existing code in backend/app/routers/.
Don't write any code yet.

Think hard about how to implement the signup endpoint.
Make a plan and wait for my approval before coding.
```

### After Plan Approval

```
Implement your plan.
Write tests first, then code to make them pass.
Run the tests after each change.
```

### Course Correction

```
Stop. That's not quite right.
The password validation should happen in the service layer, not the router.
Update your approach.
```

### Committing

```
Commit these changes. Write a clear commit message describing what was implemented.
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `/clear` | Reset context between tasks |
| `/init` | Generate CLAUDE.md for new project |
| `#` | Add instruction to CLAUDE.md mid-session |
| Escape | Interrupt current operation |
| Escape×2 | Go back in history, try different approach |
| `/permissions` | Manage tool allowlist |

## Task Files

For explicit, well-scoped work units, use task files in `tasks/`:

```
tasks/
├── TASK-01-PROJECT-SCAFFOLD.md
├── TASK-02-DATABASE-MODELS.md
├── TASK-03-AUTH-ENDPOINTS.md
└── TASK-TEMPLATE.md
```

Start a session with:

```
Read CLAUDE.md and tasks/TASK-01-PROJECT-SCAFFOLD.md.
Think hard about the implementation approach.
Make a plan and wait for my approval before coding.
```

Task files provide:
- Clear objective and scope boundaries
- Prerequisites and dependencies
- Reference to relevant docs
- Verification checklist
- Explicit "do not" list

Use `TASK-TEMPLATE.md` to create new tasks.

## When Things Go Wrong

**Claude goes in circles:**
```
Stop. You've tried this approach twice.
Let's step back. What's the actual error? Show me the relevant code.
```

**Context seems degraded:**
```
/clear
```
Then re-orient with specific file references.

**Wrong approach taken:**
- Press Escape to stop
- Press Escape twice to go back in history
- Edit your prompt and try again

## File References

- **Specs:** `docs/planning/` — Always read before implementing
- **Examples:** Point Claude to existing code that demonstrates patterns you want followed

## What NOT to Put in CLAUDE.md

- Exhaustive command lists (Claude can run `--help`)
- Detailed style guides (use a linter instead)
- Instructions for edge cases (handle when they arise)
- Anything that isn't universally applicable

## Evolving Your CLAUDE.md

Use `#` during sessions to add learnings:

```
# When writing tests, always use pytest fixtures from conftest.py
```

Claude adds this to CLAUDE.md. Periodically review and prune what isn't working.
