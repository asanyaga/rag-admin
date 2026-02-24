# Change Verifier Memory

## Project Build Notes

### Frontend
- Lint command: `npm run lint` or `npx eslint . --ext .ts,.tsx` from `frontend/`
- TypeScript check: `npx tsc --noEmit` from `frontend/`
- Build command: `npx vite build` from `frontend/` — takes ~9s
- Chunk size warning on `index-*.js` (~900 kB) is pre-existing, not a failure
- TypeScript strict mode is active — unused imports are TS6133 errors

### Common Issues
- **Unused imports = TS6133 errors.** The `Badge` import in `ChunkDetailPanel.tsx` was added
  but not used in the JSX — removed to fix. Always check that every import is actually
  referenced in the component body.

### Key Shared Components
- `src/components/shared/ChunkDetailPanel.tsx` — fetches chunk via `getChunk()`, renders
  content/stats/metadata. Accepts optional `header` ReactNode prop. Uses `Chunk` type from
  `src/types/index.ts` and `getChunk` from `src/api/indexes.ts`.

### Manual Verification Patterns
- For eval result detail changes: navigate to a completed eval run, open a result,
  click a retrieved chunk row to open the Sheet panel, verify chunk detail loads.
