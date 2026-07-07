export function CaseDetailView({ projectId, caseId }: { projectId: string | null; caseId: string }) {
  return <div data-testid="case-detail" data-project={projectId ?? ''} data-case={caseId} />
}
