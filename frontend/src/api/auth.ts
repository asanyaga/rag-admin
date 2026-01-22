import apiClient from './client'
import { AuthResponse, SignInData, SignUpData, User } from '@/types/auth'

export async function signUp(data: SignUpData): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/auth/signup', {
    email: data.email,
    password: data.password,
    password_confirm: data.passwordConfirm,
    full_name: data.fullName || undefined,
  })
  return response.data
}

export async function signIn(data: SignInData): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/auth/signin', {
    email: data.email,
    password: data.password,
  })
  return response.data
}

export async function signOut(): Promise<void> {
  await apiClient.post('/auth/signout')
}

export async function refreshToken(): Promise<{ access_token: string }> {
  const response = await apiClient.post<{ access_token: string }>('/auth/refresh')
  return response.data
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/auth/me')
  return response.data
}
