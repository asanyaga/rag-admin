# Claude Code Task: [Feature Name]

## Objective

[One or two sentences describing what this task accomplishes]

## Prerequisites

- [List completed tasks this depends on]
- [Required state or configuration]

## Reference Documents

Read these before starting:
- `CLAUDE.md` — Project conventions
- [List specific docs relevant to this task]

## Tasks

### 1. [First Major Task]

[Detailed description of what to implement]

[Code examples or signatures if helpful:]
```python
# Example structure
class ExampleService:
    def example_method(self, arg: str) -> Result:
        ...
```

### 2. [Second Major Task]

[Continue with clear, specific instructions]

### 3. Write Tests

[Specify what tests to write]

Test:
- [Test case 1]
- [Test case 2]
- [Error case 1]

## Verification Checklist

- [ ] [Specific verifiable outcome]
- [ ] [Another verifiable outcome]
- [ ] Tests pass
- [ ] No type errors

## Do Not

- [Explicit scope boundaries]
- [Things to avoid or defer]

## Notes for Next Task

[What comes after this task, if relevant]

---

# Template Usage Notes (delete this section when using)

## Effective Task Design Principles

1. **Single Responsibility** — Each task should be completable in one focused session (30-90 minutes of work)

2. **Clear Boundaries** — Explicitly state what's in scope and what's not

3. **Concrete Outputs** — Every task should produce verifiable artifacts (files, passing tests, working endpoints)

4. **Reference, Don't Repeat** — Point to docs rather than duplicating specs

5. **Testable Criteria** — The verification checklist should be unambiguous

## Task Sizing Guidelines

| Size | Scope | Examples |
|------|-------|----------|
| Small | Single file or function | Add a utility, write tests for existing code |
| Medium | One feature slice | Single endpoint with service and tests |
| Large | Full feature | Auth system, CRUD for an entity (split into multiple tasks) |

If a task feels larger than "medium," split it.

## Prompting Tips for Claude Code

**Starting a task:**
```
I'm working on RAG Admin. Please read CLAUDE.md and TASK-XX-[name].md, 
then tell me your implementation plan before writing code.
```

**Mid-task check-in:**
```
Before continuing, show me the current state of [file] and confirm 
it matches what we discussed.
```

**Completing a task:**
```
Run through the verification checklist in the task file and report status.
Update CLAUDE.md if any conventions changed.
```

**When something goes wrong:**
```
Stop. Show me the error, the relevant code, and the file paths involved.
Don't attempt to fix until I confirm the approach.
```