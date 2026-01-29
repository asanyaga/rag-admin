import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { AlertCircle, Loader2 } from 'lucide-react'

function getErrorMessage(code: string | null, message: string | null): string {
  // Use custom message if provided
  if (message) {
    return message
  }

  // Otherwise map error codes to user-friendly messages
  switch (code) {
    case 'OAUTH_FAILED':
      return 'Sign in with Google failed. Please try again.'
    case 'INVALID_STATE':
      return 'Something went wrong. Please try again.'
    case 'EMAIL_EXISTS_DIFFERENT_PROVIDER':
      return 'This email is already registered. Please sign in with your email and password.'
    default:
      return 'Something went wrong. Please try again.'
  }
}

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const { completeOAuthSignIn } = useAuth()
  const [status, setStatus] = useState<'loading' | 'error'>('loading')
  const [errorMessage, setErrorMessage] = useState<string>('')

  useEffect(() => {
    const handleSuccess = async () => {
      try {
        await completeOAuthSignIn()
        navigate('/', { replace: true })
      } catch (error) {
        setStatus('error')
        setErrorMessage(
          error instanceof Error
            ? error.message
            : 'Failed to complete sign in. Please try again.'
        )
      }
    }

    const handleError = (code: string | null, message: string | null) => {
      setStatus('error')
      setErrorMessage(getErrorMessage(code, message))
    }

    const handleCallback = async () => {
      const params = new URLSearchParams(window.location.search)

      if (params.get('success') === 'true') {
        await handleSuccess()
      } else if (params.get('error')) {
        handleError(params.get('error'), params.get('message'))
      } else {
        // No success or error parameter - something went wrong
        handleError(null, 'Invalid callback parameters')
      }
    }

    handleCallback()
  }, [completeOAuthSignIn, navigate])

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Completing sign in...</p>
        </div>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center min-h-screen p-6">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive" />
            <h2 className="text-xl font-semibold mb-2">Sign in failed</h2>
            <p className="text-muted-foreground mb-6">{errorMessage}</p>
            <div className="flex flex-col gap-2">
              <Button onClick={() => navigate('/signin')} className="w-full">
                Back to sign in
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return null
}
