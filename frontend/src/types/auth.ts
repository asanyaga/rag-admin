export interface User {
  id: string
  email: string
  fullName: string | null
  authProvider: 'local' | 'google'
  createdAt: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface SignInData {
  email: string
  password: string
}

export interface SignUpData {
  email: string
  password: string
  passwordConfirm: string
  fullName?: string
}
