/**
 * Hook for managing provider API keys
 */
import { useState, useCallback, useEffect } from 'react'
import {
  ProviderKey,
  ProviderKeyCreate,
  ProviderInfo,
} from '@/types/index'
import * as providerKeysApi from '@/api/providerKeys'

interface UseProviderKeysReturn {
  providers: ProviderInfo[]
  accountKeys: ProviderKey[]
  isLoading: boolean
  error: string | null
  fetchProviders: () => Promise<void>
  fetchAccountKeys: () => Promise<void>
  setAccountKey: (data: ProviderKeyCreate) => Promise<ProviderKey>
  deleteAccountKey: (provider: string) => Promise<void>
  hasKeyForProvider: (provider: string) => boolean
}

export function useProviderKeys(): UseProviderKeysReturn {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [accountKeys, setAccountKeys] = useState<ProviderKey[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProviders = useCallback(async () => {
    try {
      const data = await providerKeysApi.listProviders()
      setProviders(data.providers)
    } catch (err) {
      console.error('Error fetching providers:', err)
    }
  }, [])

  const fetchAccountKeys = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await providerKeysApi.listAccountKeys()
      setAccountKeys(data.keys)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch API keys'
      setError(errorMessage)
      console.error('Error fetching account keys:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const setAccountKey = useCallback(
    async (data: ProviderKeyCreate): Promise<ProviderKey> => {
      try {
        const key = await providerKeysApi.setAccountKey(data)

        // Update or add in list
        setAccountKeys((prev) => {
          const existing = prev.find((k) => k.provider === data.provider)
          if (existing) {
            return prev.map((k) => (k.provider === data.provider ? key : k))
          }
          return [...prev, key]
        })

        return key
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to save API key'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  const deleteAccountKey = useCallback(async (provider: string): Promise<void> => {
    try {
      await providerKeysApi.deleteAccountKey(provider)
      setAccountKeys((prev) => prev.filter((k) => k.provider !== provider))
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to delete API key'
      setError(errorMessage)
      throw err
    }
  }, [])

  const hasKeyForProvider = useCallback(
    (provider: string): boolean => {
      return accountKeys.some((k) => k.provider === provider)
    },
    [accountKeys]
  )

  // Fetch on mount
  useEffect(() => {
    fetchProviders()
    fetchAccountKeys()
  }, [fetchProviders, fetchAccountKeys])

  return {
    providers,
    accountKeys,
    isLoading,
    error,
    fetchProviders,
    fetchAccountKeys,
    setAccountKey,
    deleteAccountKey,
    hasKeyForProvider,
  }
}
