/**
 * Provider Keys API client functions
 */
import apiClient from './client'
import {
  ProviderKey,
  ProviderKeyCreate,
  ProviderListResponse,
} from '@/types/index'

// List supported providers
export async function listProviders(): Promise<ProviderListResponse> {
  const response = await apiClient.get<ProviderListResponse>(
    '/settings/provider-keys/providers'
  )
  return response.data
}

// List account-level keys
export async function listAccountKeys(): Promise<{ keys: ProviderKey[] }> {
  const response = await apiClient.get<{ keys: ProviderKey[] }>(
    '/settings/provider-keys'
  )
  return response.data
}

// Set account-level key
export async function setAccountKey(
  data: ProviderKeyCreate
): Promise<ProviderKey> {
  const response = await apiClient.post<ProviderKey>(
    '/settings/provider-keys',
    { provider: data.provider, apiKey: data.apiKey }
  )
  return response.data
}

// Delete account-level key
export async function deleteAccountKey(provider: string): Promise<void> {
  await apiClient.delete(`/settings/provider-keys/${provider}`)
}

// List project-level keys
export async function listProjectKeys(
  projectId: string
): Promise<{ keys: ProviderKey[] }> {
  const response = await apiClient.get<{ keys: ProviderKey[] }>(
    `/projects/${projectId}/settings/provider-keys`
  )
  return response.data
}

// Set project-level key
export async function setProjectKey(
  projectId: string,
  data: ProviderKeyCreate
): Promise<ProviderKey> {
  const response = await apiClient.post<ProviderKey>(
    `/projects/${projectId}/settings/provider-keys`,
    { provider: data.provider, apiKey: data.apiKey }
  )
  return response.data
}

// Delete project-level key
export async function deleteProjectKey(
  projectId: string,
  provider: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectId}/settings/provider-keys/${provider}`
  )
}
