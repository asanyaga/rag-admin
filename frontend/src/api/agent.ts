import apiClient from './client'
import type {
  AgentType,
  AgentConfig,
  AgentConfigCreate,
  AgentReceipt,
  AgentReceiptListItem,
  StartProcessingRequest,
  SubmitReviewRequest,
} from '@/types/agent'

// --- Agent Types ---

export async function listAgentTypes(): Promise<AgentType[]> {
  const response = await apiClient.get<AgentType[]>('/agent/types')
  return response.data
}

// --- Agent Configs ---

export async function listAgentConfigs(
  projectId: string
): Promise<AgentConfig[]> {
  const response = await apiClient.get<AgentConfig[]>(
    `/agent/projects/${projectId}/configs`
  )
  return response.data
}

export async function createAgentConfig(
  projectId: string,
  data: AgentConfigCreate
): Promise<AgentConfig> {
  const response = await apiClient.post<AgentConfig>(
    `/agent/projects/${projectId}/configs`,
    data
  )
  return response.data
}

export async function deleteAgentConfig(
  configId: string
): Promise<void> {
  await apiClient.delete(`/agent/configs/${configId}`)
}

// --- Receipt Processing ---

export async function startProcessing(
  projectId: string,
  data: StartProcessingRequest
): Promise<AgentReceipt> {
  const response = await apiClient.post<AgentReceipt>(
    `/agent/projects/${projectId}/receipts`,
    data
  )
  return response.data
}

export async function listReceipts(
  projectId: string
): Promise<AgentReceiptListItem[]> {
  const response = await apiClient.get<AgentReceiptListItem[]>(
    `/agent/projects/${projectId}/receipts`
  )
  return response.data
}

export async function getReceipt(
  receiptId: string
): Promise<AgentReceipt> {
  const response = await apiClient.get<AgentReceipt>(
    `/agent/receipts/${receiptId}`
  )
  return response.data
}

export async function submitReview(
  receiptId: string,
  data: SubmitReviewRequest
): Promise<AgentReceipt> {
  const response = await apiClient.post<AgentReceipt>(
    `/agent/receipts/${receiptId}/review`,
    data
  )
  return response.data
}
