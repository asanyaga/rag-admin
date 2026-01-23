import {
  createContext,
  ReactNode,
  useEffect,
  useState,
  useCallback,
} from 'react'
import { User, SignUpData, SignInData } from '@/types/auth'
import * as authApi from '@/api/auth'
import { setAccessToken } from '@/api/client'
import { getCookie, deleteCookie } from '@/utils/cookies'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (data: SignUpData) => Promise<void>
  signOut: () => Promise<void>
  completeOAuthSignIn: () => Promise<void>
  initiateGoogleSignIn: () => void
}

export const AuthContext = createContext<AuthContextType | undefined>(
  undefined
)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Attempt to restore session on mount
  useEffect(() => {
    const initAuth = async () => {
      // Skip refresh attempt if on public auth pages to avoid unnecessary API calls
      const publicPaths = ['/signin', '/signup', '/auth/callback']
      if (publicPaths.includes(window.location.pathname)) {
        setIsLoading(false)
        return
      }

      try {
        // Try to refresh token and get user
        const { access_token } = await authApi.refreshToken()
        setAccessToken(access_token)
        const currentUser = await authApi.getCurrentUser()
        setUser(currentUser)
      } catch (error) {
        // No valid session, user needs to sign in
        setAccessToken(null)
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const data: SignInData = { email, password }
    const response = await authApi.signIn(data)
    setAccessToken(response.access_token)
    setUser(response.user)
  }, [])

  const signUp = useCallback(async (data: SignUpData) => {
    const response = await authApi.signUp(data)
    setAccessToken(response.access_token)
    setUser(response.user)
  }, [])

  const signOut = useCallback(async () => {
    try {
      await authApi.signOut()
    } catch (error) {
      // Ignore errors on sign out
    } finally {
      setAccessToken(null)
      setUser(null)
    }
  }, [])

  const initiateGoogleSignIn = useCallback(() => {
    // Redirect to backend OAuth endpoint
    window.location.href = '/api/v1/auth/google/authorize'
  }, [])

  const completeOAuthSignIn = useCallback(async () => {
    // Get access token from cookie set by backend
    const accessToken = getCookie('access_token')
    if (!accessToken) {
      throw new Error('No access token found')
    }

    // Store token in memory
    setAccessToken(accessToken)

    // Delete temporary cookie
    deleteCookie('access_token')

    // Fetch current user
    const currentUser = await authApi.getCurrentUser()
    setUser(currentUser)
  }, [])

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    signIn,
    signUp,
    signOut,
    completeOAuthSignIn,
    initiateGoogleSignIn,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
