import apiClient from './client'
import type {
  AgentTool,
  AgentDefinition,
  AgentDefinitionCreate,
  AgentDefinitionUpdate,
  AgentRun,
  AgentRunListItem,
  StartAgentRunRequest,
  StartExtractRunRequest,
  StartParseRunRequest,
  ResumeAgentRunRequest,
} from '@/types/agent'

// --- Agent Tools ---

export async function listAgentTools(): Promise<AgentTool[]> {
  const response = await apiClient.get<AgentTool[]>('/agent/tools')
  return response.data
}

// --- Agent Definitions ---

export async function listAgentDefinitions(
  projectId: string
): Promise<AgentDefinition[]> {
  const response = await apiClient.get<AgentDefinition[]>(
    `/agent/projects/${projectId}/definitions`
  )
  return response.data
}

export async function getAgentDefinition(
  agentId: string
): Promise<AgentDefinition> {
  const response = await apiClient.get<AgentDefinition>(
    `/agent/definitions/${agentId}`
  )
  return response.data
}

export async function createAgentDefinition(
  projectId: string,
  data: AgentDefinitionCreate
): Promise<AgentDefinition> {
  const response = await apiClient.post<AgentDefinition>(
    `/agent/projects/${projectId}/definitions`,
    data
  )
  return response.data
}

export async function updateAgentDefinition(
  agentId: string,
  data: AgentDefinitionUpdate
): Promise<AgentDefinition> {
  const response = await apiClient.put<AgentDefinition>(
    `/agent/definitions/${agentId}`,
    data
  )
  return response.data
}

export async function deleteAgentDefinition(
  agentId: string
): Promise<void> {
  await apiClient.delete(`/agent/definitions/${agentId}`)
}

// --- Agent Runs ---

export async function startAgentRun(
  projectId: string,
  data: StartAgentRunRequest
): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(
    `/agent/projects/${projectId}/runs`,
    data
  )
  return response.data
}

export async function startExtractRun(
  projectId: string,
  data: StartExtractRunRequest
): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(
    `/agent/extract/projects/${projectId}/runs`,
    data
  )
  return response.data
}

export async function startParseRun(
  projectId: string,
  data: StartParseRunRequest
): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(
    `/agent/parse/projects/${projectId}/runs`,
    data
  )
  return response.data
}

export async function listAgentRuns(
  projectId: string
): Promise<AgentRunListItem[]> {
  const response = await apiClient.get<AgentRunListItem[]>(
    `/agent/projects/${projectId}/runs`
  )
  return response.data
}

export async function getAgentRun(
  runId: string
): Promise<AgentRun> {
  const response = await apiClient.get<AgentRun>(
    `/agent/runs/${runId}`
  )
  return response.data
}

export async function resumeAgentRun(
  runId: string,
  data: ResumeAgentRunRequest
): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(
    `/agent/runs/${runId}/resume`,
    data
  )
  return response.data
}

export async function deleteAgentRun(
  runId: string
): Promise<void> {
  await apiClient.delete(`/agent/runs/${runId}`)
}
