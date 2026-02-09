/**
 * Settings page with provider API key management
 */
import { useState } from 'react'
import { useProviderKeys } from '@/hooks/useProviderKeys'
import { ProviderKeyCreate } from '@/types/index'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Key, Plus, Trash2, Check, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

export default function SettingsPage() {
  const {
    providers,
    accountKeys,
    isLoading,
    error,
    setAccountKey,
    deleteAccountKey,
    hasKeyForProvider,
  } = useProviderKeys()

  const [addKeyDialogOpen, setAddKeyDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)
  const [newKeyData, setNewKeyData] = useState<ProviderKeyCreate>({
    provider: '',
    apiKey: '',
  })
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleAddKey = async () => {
    if (!newKeyData.provider || !newKeyData.apiKey) {
      toast.error('Please select a provider and enter an API key')
      return
    }

    setIsSaving(true)
    try {
      await setAccountKey(newKeyData)
      setAddKeyDialogOpen(false)
      setNewKeyData({ provider: '', apiKey: '' })
      toast.success('API key saved successfully')
    } catch {
      // Error handled by hook
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteClick = (provider: string) => {
    setSelectedProvider(provider)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedProvider) return

    setIsDeleting(true)
    try {
      await deleteAccountKey(selectedProvider)
      setDeleteDialogOpen(false)
      setSelectedProvider(null)
      toast.success('API key deleted')
    } catch {
      // Error handled by hook
    } finally {
      setIsDeleting(false)
    }
  }

  // Providers that need API keys
  const keyProviders = providers.filter((p) => p.requiresKey)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your account settings and API keys
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* API Keys Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                API Keys
              </CardTitle>
              <CardDescription className="mt-1.5">
                Configure your embedding provider API keys. These keys are
                encrypted and stored securely.
              </CardDescription>
            </div>
            <Button onClick={() => setAddKeyDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Key
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          ) : keyProviders.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Loading providers...
            </p>
          ) : (
            <div className="space-y-3">
              {keyProviders.map((provider) => {
                const hasKey = hasKeyForProvider(provider.name)
                const keyInfo = accountKeys.find(
                  (k) => k.provider === provider.name
                )

                return (
                  <div
                    key={provider.name}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-2 rounded-full ${
                          hasKey
                            ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {hasKey ? (
                          <Check className="h-4 w-4" />
                        ) : (
                          <AlertTriangle className="h-4 w-4" />
                        )}
                      </div>
                      <div>
                        <div className="font-medium">{provider.displayName}</div>
                        <div className="text-sm text-muted-foreground">
                          {hasKey ? (
                            <span className="font-mono">{keyInfo?.apiKeyMasked}</span>
                          ) : (
                            'No key configured'
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {hasKey && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteClick(provider.name)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                      <Button
                        variant={hasKey ? 'outline' : 'default'}
                        size="sm"
                        onClick={() => {
                          setNewKeyData({ provider: provider.name, apiKey: '' })
                          setAddKeyDialogOpen(true)
                        }}
                      >
                        {hasKey ? 'Update' : 'Add Key'}
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          <p className="text-xs text-muted-foreground mt-4">
            API keys are encrypted at rest and only decrypted when making API
            calls. You can also set project-level keys that override these
            account-level keys.
          </p>
        </CardContent>
      </Card>

      {/* Add Key Dialog */}
      <Dialog open={addKeyDialogOpen} onOpenChange={setAddKeyDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add API Key</DialogTitle>
            <DialogDescription>
              Enter your API key for the selected embedding provider.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select
                value={newKeyData.provider}
                onValueChange={(v) =>
                  setNewKeyData((prev) => ({ ...prev, provider: v }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {keyProviders.map((provider) => (
                    <SelectItem key={provider.name} value={provider.name}>
                      {provider.displayName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder="sk-..."
                value={newKeyData.apiKey}
                onChange={(e) =>
                  setNewKeyData((prev) => ({ ...prev, apiKey: e.target.value }))
                }
              />
              <p className="text-xs text-muted-foreground">
                Your key will be encrypted before storage.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setAddKeyDialogOpen(false)
                setNewKeyData({ provider: '', apiKey: '' })
              }}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button onClick={handleAddKey} disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save Key'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete API Key</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the{' '}
              {providers.find((p) => p.name === selectedProvider)?.displayName}{' '}
              API key? Indexes using this provider will fail to process until a
              new key is added.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
