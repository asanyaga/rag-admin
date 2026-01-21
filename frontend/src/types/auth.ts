export interface User {
  id: string
  email: string
  fullName: string | null
  authProvider: 'local' | 'google'
  createdAt: string
}

export interface AuthResponse {
  accessToken: string
  tokenType: string
  expiresIn: number
  user: User
}

export interface SignInRequest {
  email: string
  password: string
}

export interface SignUpRequest {
  email: string
  password: string
  passwordConfirm: string
  fullName?: string
}
