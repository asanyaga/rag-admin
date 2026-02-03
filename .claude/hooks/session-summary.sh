#!/bin/bash
# Session summary generator for SessionEnd hook
# Called by Claude Code SessionEnd hook

set -e

# Read JSON input from stdin
INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
CWD=$(echo "$INPUT" | jq -r '.cwd')
REASON=$(echo "$INPUT" | jq -r '.reason')

# Skip if transcript doesn't exist or is empty
if [ ! -f "$TRANSCRIPT_PATH" ] || [ ! -s "$TRANSCRIPT_PATH" ]; then
  echo "No transcript found, skipping summary generation"
  exit 0
fi

# Skip for very short sessions (less than 10 lines in transcript)
LINE_COUNT=$(wc -l < "$TRANSCRIPT_PATH")
if [ "$LINE_COUNT" -lt 10 ]; then
  echo "Session too short ($LINE_COUNT lines), skipping summary"
  exit 0
fi

# Use Claude Code CLI in non-interactive mode to generate summary
cd "$CWD"
claude --print --dangerously-skip-permissions <<PROMPT
You are generating a session summary for docs/session-log.md.

The session transcript is at: $TRANSCRIPT_PATH

**Your task:**
1. Read the transcript file to extract:
   - Usage statistics (total tokens by model, cache hits, costs)
   - API duration and wall clock duration
   - Code changes made (files modified, lines added/removed)
   - Tasks worked on
   - Key accomplishments and learnings

2. Generate a session summary following this EXACT format:

## $(date +%Y-%m-%d): [Brief descriptive title]

**Goal:** [What was intended to be accomplished]
**Outcome:** [What actually happened - use checkmarks for completed items]
**Learned:** [Key concepts, patterns, or design decisions discovered]
**Tasks:** [Task IDs worked on, e.g., #1, #3]
**Next:** [What should be done in the next session]
**Total cost:** [Total session cost from transcript, e.g., \$0.42]
**Total duration (API):** [Total API time from transcript]
**Total duration (wall):** [Total wall clock time]
**Total code changes:** [Files modified and approximate line changes]
**Usage by model:**
    **model-name:** X input, Y output, Z cache read, W cache write (model total cost e.g. \$0.15)

3. Append the formatted entry to docs/session-log.md under the "## Sessions" section

**Session context:**
- Working directory: $CWD
- Session ID: $SESSION_ID
- Exit reason: $REASON

Generate and append the summary now.
PROMPT
