import { useAuth } from '@/hooks/useAuth'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export default function HomePage() {
  const { user } = useAuth()

  return (
    <div>
      <Card className="max-w-2xl">
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
    </div>
  )
}
