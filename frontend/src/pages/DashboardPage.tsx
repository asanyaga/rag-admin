import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useNavigate } from 'react-router-dom'

export default function DashboardPage() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    await signOut()
    navigate('/signin', { replace: true })
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">RAG Admin</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {user?.fullName || user?.email}
            </span>
            <Button variant="outline" onClick={handleSignOut}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle>Welcome to RAG Admin!</CardTitle>
            <CardDescription>
              You're successfully signed in as {user?.email}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <p className="text-muted-foreground">
                RAG Admin dashboard coming soon
              </p>
              <div className="bg-muted p-4 rounded-md">
                <h3 className="font-semibold mb-2">Your Account</h3>
                <dl className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Email:</dt>
                    <dd>{user?.email}</dd>
                  </div>
                  {user?.fullName && (
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Name:</dt>
                      <dd>{user.fullName}</dd>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Provider:</dt>
                    <dd className="capitalize">{user?.authProvider}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Member since:</dt>
                    <dd>
                      {user?.createdAt
                        ? new Date(user.createdAt).toLocaleDateString()
                        : 'N/A'}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
