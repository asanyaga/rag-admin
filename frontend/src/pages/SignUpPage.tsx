import { useState, FormEvent, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { PasswordStrengthIndicator } from '@/components/PasswordStrengthIndicator'
import { toast } from 'sonner'
import { AxiosError } from 'axios'
// import { GoogleIcon } from '@/components/icons/GoogleIcon' // Disabled for initial deployment

export default function SignUpPage() {
  const navigate = useNavigate()
  const { signUp, isAuthenticated, initiateGoogleSignIn } = useAuth()

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    passwordConfirm: '',
    fullName: '',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const validateEmail = (email: string): string | null => {
    if (!email) {
      return 'Email is required'
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      return 'Please enter a valid email address'
    }
    return null
  }

  const validatePassword = (password: string): string | null => {
    if (!password) {
      return 'Password is required'
    }
    if (password.length < 8) {
      return 'Password must be at least 8 characters'
    }
    if (!/[A-Z]/.test(password)) {
      return 'Password must contain at least one uppercase letter'
    }
    if (!/[a-z]/.test(password)) {
      return 'Password must contain at least one lowercase letter'
    }
    if (!/[0-9]/.test(password)) {
      return 'Password must contain at least one number'
    }
    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
      return 'Password must contain at least one special character'
    }
    return null
  }

  const validatePasswordConfirm = (
    password: string,
    passwordConfirm: string
  ): string | null => {
    if (!passwordConfirm) {
      return 'Please confirm your password'
    }
    if (password !== passwordConfirm) {
      return 'Passwords do not match'
    }
    return null
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    // Reset errors
    setErrors({})

    // Validate all fields
    const newErrors: Record<string, string> = {}

    const emailError = validateEmail(formData.email)
    if (emailError) newErrors.email = emailError

    const passwordError = validatePassword(formData.password)
    if (passwordError) newErrors.password = passwordError

    const passwordConfirmError = validatePasswordConfirm(
      formData.password,
      formData.passwordConfirm
    )
    if (passwordConfirmError) newErrors.passwordConfirm = passwordConfirmError

    // If there are errors, show them and return
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setIsSubmitting(true)

    try {
      await signUp(formData)
      navigate('/', { replace: true })
    } catch (error) {
      if (error instanceof AxiosError) {
        const errorData = error.response?.data
        if (errorData?.detail) {
          // Check for specific error messages
          if (
            typeof errorData.detail === 'string' &&
            errorData.detail.toLowerCase().includes('already exists')
          ) {
            setErrors({ email: 'An account with this email already exists' })
          } else if (typeof errorData.detail === 'string') {
            toast.error(errorData.detail)
          } else {
            toast.error('Something went wrong. Please try again')
          }
        } else {
          toast.error('Something went wrong. Please try again')
        }
      } else {
        toast.error('Something went wrong. Please try again')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <Card>
          <CardHeader>
            <CardTitle>Create your account</CardTitle>
            <CardDescription>
              Enter your details below to create your account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit}>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="email">Email</FieldLabel>
                  <Input
                    id="email"
                    type="email"
                    placeholder="m@example.com"
                    value={formData.email}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    disabled={isSubmitting}
                    autoFocus
                    required
                    className={errors.email ? 'border-destructive' : ''}
                  />
                  {errors.email && (
                    <FieldDescription className="text-destructive">
                      {errors.email}
                    </FieldDescription>
                  )}
                </Field>

                <Field>
                  <FieldLabel htmlFor="fullName">Full Name (Optional)</FieldLabel>
                  <Input
                    id="fullName"
                    type="text"
                    placeholder="John Doe"
                    value={formData.fullName}
                    onChange={(e) =>
                      setFormData({ ...formData, fullName: e.target.value })
                    }
                    disabled={isSubmitting}
                  />
                </Field>

                <Field>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) =>
                      setFormData({ ...formData, password: e.target.value })
                    }
                    disabled={isSubmitting}
                    required
                    className={errors.password ? 'border-destructive' : ''}
                  />
                  {errors.password && (
                    <FieldDescription className="text-destructive">
                      {errors.password}
                    </FieldDescription>
                  )}
                  <PasswordStrengthIndicator password={formData.password} />
                </Field>

                <Field>
                  <FieldLabel htmlFor="passwordConfirm">
                    Confirm Password
                  </FieldLabel>
                  <Input
                    id="passwordConfirm"
                    type="password"
                    value={formData.passwordConfirm}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        passwordConfirm: e.target.value,
                      })
                    }
                    disabled={isSubmitting}
                    required
                    className={errors.passwordConfirm ? 'border-destructive' : ''}
                  />
                  {errors.passwordConfirm && (
                    <FieldDescription className="text-destructive">
                      {errors.passwordConfirm}
                    </FieldDescription>
                  )}
                </Field>

                <Field>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? 'Creating account...' : 'Sign up'}
                  </Button>
                  {/* Google OAuth disabled for initial deployment
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={initiateGoogleSignIn}
                    disabled={isSubmitting}
                  >
                    <GoogleIcon className="mr-2 h-4 w-4" />
                    Sign up with Google
                  </Button>
                  */}
                  <FieldDescription className="text-center">
                    Already have an account?{' '}
                    <Link to="/signin" className="underline underline-offset-4">
                      Sign in
                    </Link>
                  </FieldDescription>
                </Field>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
