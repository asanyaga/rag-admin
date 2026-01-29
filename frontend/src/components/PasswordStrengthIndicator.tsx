import { Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PasswordStrengthIndicatorProps {
  password: string
}

interface Requirement {
  label: string
  test: (password: string) => boolean
}

const requirements: Requirement[] = [
  {
    label: 'At least 8 characters',
    test: (pwd) => pwd.length >= 8,
  },
  {
    label: 'At least one uppercase letter',
    test: (pwd) => /[A-Z]/.test(pwd),
  },
  {
    label: 'At least one lowercase letter',
    test: (pwd) => /[a-z]/.test(pwd),
  },
  {
    label: 'At least one number',
    test: (pwd) => /[0-9]/.test(pwd),
  },
  {
    label: 'At least one special character',
    test: (pwd) => /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pwd),
  },
]

export function PasswordStrengthIndicator({
  password,
}: PasswordStrengthIndicatorProps) {
  if (!password) {
    return null
  }

  const metRequirements = requirements.filter((req) => req.test(password))
  const strength = metRequirements.length
  const totalRequirements = requirements.length

  // Calculate strength level
  let strengthLevel: 'weak' | 'medium' | 'strong' = 'weak'
  let strengthColor = 'bg-destructive'

  if (strength === totalRequirements) {
    strengthLevel = 'strong'
    strengthColor = 'bg-green-500'
  } else if (strength >= 3) {
    strengthLevel = 'medium'
    strengthColor = 'bg-yellow-500'
  }

  return (
    <div className="space-y-2 mt-2">
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn('h-full transition-all duration-300', strengthColor)}
            style={{
              width: `${(strength / totalRequirements) * 100}%`,
            }}
          />
        </div>
        <span className="text-xs text-muted-foreground capitalize">
          {strengthLevel}
        </span>
      </div>

      <div className="space-y-1">
        {requirements.map((req, index) => {
          const isMet = req.test(password)
          return (
            <div
              key={index}
              className={cn(
                'flex items-center gap-2 text-xs',
                isMet ? 'text-green-600' : 'text-muted-foreground'
              )}
            >
              {isMet ? (
                <Check className="h-3 w-3" />
              ) : (
                <X className="h-3 w-3" />
              )}
              <span>{req.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
