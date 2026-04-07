import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Plus, Trash2 } from 'lucide-react'

interface DynamicFieldFormProps {
  schemaDefinition: Record<string, unknown>
  data: Record<string, unknown>
  onChange: (data: Record<string, unknown>) => void
}

export function DynamicFieldForm({
  schemaDefinition,
  data,
  onChange,
}: DynamicFieldFormProps) {
  const properties = (schemaDefinition.properties ?? {}) as Record<
    string,
    { type?: string; items?: { properties?: Record<string, { type?: string }> } }
  >

  const handleFieldChange = (key: string, value: unknown) => {
    onChange({ ...data, [key]: value })
  }

  const handleLineItemChange = (
    key: string,
    index: number,
    field: string,
    value: unknown
  ) => {
    const items = [...((data[key] as Array<Record<string, unknown>>) || [])]
    items[index] = { ...items[index], [field]: value }
    onChange({ ...data, [key]: items })
  }

  const addLineItem = (key: string, itemProps: Record<string, { type?: string }>) => {
    const items = [...((data[key] as Array<Record<string, unknown>>) || [])]
    const newItem: Record<string, unknown> = {}
    for (const prop of Object.keys(itemProps)) {
      newItem[prop] = itemProps[prop].type === 'number' ? 0 : ''
    }
    items.push(newItem)
    onChange({ ...data, [key]: items })
  }

  const removeLineItem = (key: string, index: number) => {
    const items = [...((data[key] as Array<Record<string, unknown>>) || [])]
    items.splice(index, 1)
    onChange({ ...data, [key]: items })
  }

  return (
    <div className="space-y-4">
      {Object.entries(properties).map(([key, schema]) => {
        if (schema.type === 'array' && schema.items?.properties) {
          // Array field (line items)
          const itemProps = schema.items.properties
          const items = (data[key] as Array<Record<string, unknown>>) || []

          return (
            <div key={key} className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium capitalize">
                  {key.replace(/_/g, ' ')}
                </Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => addLineItem(key, itemProps)}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add
                </Button>
              </div>
              <div className="space-y-2 pl-2 border-l-2 border-muted">
                {items.map((item, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-2 rounded-md border p-2"
                  >
                    <div className="flex-1 grid grid-cols-2 gap-2">
                      {Object.entries(itemProps).map(([prop, propSchema]) => (
                        <div key={prop}>
                          <Label className="text-xs text-muted-foreground capitalize">
                            {prop.replace(/_/g, ' ')}
                          </Label>
                          <Input
                            type={propSchema.type === 'number' ? 'number' : 'text'}
                            value={String(item[prop] ?? '')}
                            onChange={(e) =>
                              handleLineItemChange(
                                key,
                                index,
                                prop,
                                propSchema.type === 'number'
                                  ? parseFloat(e.target.value) || 0
                                  : e.target.value
                              )
                            }
                            className="h-8 text-sm"
                          />
                        </div>
                      ))}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0 mt-4"
                      onClick={() => removeLineItem(key, index)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )
        }

        // Scalar field
        const fieldType = schema.type === 'number' ? 'number' : 'text'
        return (
          <div key={key} className="space-y-1.5">
            <Label className="text-sm capitalize">
              {key.replace(/_/g, ' ')}
            </Label>
            <Input
              type={fieldType}
              value={String(data[key] ?? '')}
              onChange={(e) =>
                handleFieldChange(
                  key,
                  schema.type === 'number'
                    ? parseFloat(e.target.value) || 0
                    : e.target.value
                )
              }
            />
          </div>
        )
      })}
    </div>
  )
}
