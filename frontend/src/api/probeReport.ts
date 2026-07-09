import apiClient from './client'
import type { ProbeConfig, ProbeReport } from '@/types/probeReport'

export async function probeDocument(
  documentId: string,
  config: ProbeConfig | null = null,
): Promise<ProbeReport> {
  const { data } = await apiClient.post<ProbeReport>('/probe', {
    document_id: documentId,
    config,
  })
  return data
}
