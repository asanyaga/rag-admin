import apiClient from './client'
import type {
  ParseAgentRunDetail,
  ParseAgentRunSummary,
  StartParseAgentRunRequest,
} from '@/types/parseAgent'

export async function startParseAgentRun(
  req: StartParseAgentRunRequest
): Promise<{ runId: string }> {
  const form = new FormData()
  form.append('project_id', req.projectId)
  form.append('parser_type', req.parserType ?? 'simple')
  if (req.parseConfig) form.append('parse_config', req.parseConfig)
  form.append('file', req.file)

  const response = await apiClient.post<{ runId: string }>(
    '/parse-agent-runs',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}

export async function getParseAgentRun(
  runId: string
): Promise<ParseAgentRunDetail> {
  const response = await apiClient.get<ParseAgentRunDetail>(
    `/parse-agent-runs/${runId}`
  )
  return response.data
}

export async function listParseAgentRuns(
  projectId: string
): Promise<ParseAgentRunSummary[]> {
  const response = await apiClient.get<ParseAgentRunSummary[]>(
    '/parse-agent-runs',
    { params: { project_id: projectId } }
  )
  return response.data
}
