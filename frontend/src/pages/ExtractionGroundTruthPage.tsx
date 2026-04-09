import { useReducer, useCallback } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import {
  useExtractionGroundTruthSets,
  useExtractionGroundTruthItems,
} from '@/hooks/useExtractionGroundTruth'
import type { ExtractionGroundTruthSet, ExtractionGroundTruthItem } from '@/types/extractionGroundTruth'
import type { ExtractionSchema } from '@/types/extraction'
import { GroundTruthSetList } from '@/components/extraction-ground-truth/GroundTruthSetList'
import { GroundTruthSetDetail } from '@/components/extraction-ground-truth/GroundTruthSetDetail'
import { GroundTruthEditor } from '@/components/extraction-ground-truth/GroundTruthEditor'
import { toast } from 'sonner'

// ---------------------------------------------------------------------------
// Navigation state — discriminated union ensures consistency
// ---------------------------------------------------------------------------
type NavState =
  | { view: 'list'; selectedSet: null; editingItem: null }
  | { view: 'detail'; selectedSet: ExtractionGroundTruthSet; editingItem: null }
  | { view: 'editor'; selectedSet: ExtractionGroundTruthSet; editingItem: ExtractionGroundTruthItem }

type NavAction =
  | { type: 'SELECT_SET'; set: ExtractionGroundTruthSet }
  | { type: 'EDIT_ITEM'; item: ExtractionGroundTruthItem }
  | { type: 'NAVIGATE_ITEM'; item: ExtractionGroundTruthItem }
  | { type: 'BACK_TO_LIST' }
  | { type: 'BACK_TO_DETAIL' }

function navReducer(state: NavState, action: NavAction): NavState {
  switch (action.type) {
    case 'SELECT_SET':
      return { view: 'detail', selectedSet: action.set, editingItem: null }
    case 'EDIT_ITEM':
      if (state.view === 'detail') {
        return { view: 'editor', selectedSet: state.selectedSet, editingItem: action.item }
      }
      return state
    case 'NAVIGATE_ITEM':
      if (state.view === 'editor') {
        return { ...state, editingItem: action.item }
      }
      return state
    case 'BACK_TO_LIST':
      return { view: 'list', selectedSet: null, editingItem: null }
    case 'BACK_TO_DETAIL':
      if (state.view === 'editor') {
        return { view: 'detail', selectedSet: state.selectedSet, editingItem: null }
      }
      return state
    default:
      return state
  }
}

const initialNavState: NavState = { view: 'list', selectedSet: null, editingItem: null }

export default function ExtractionGroundTruthPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const { documents } = useDocuments(projectId)
  const { schemas } = useExtractionSchemas(projectId)
  const { sets, isLoading: setsLoading, createSet, deleteSet, fetchSets } = useExtractionGroundTruthSets(projectId)

  const [nav, dispatch] = useReducer(navReducer, initialNavState)

  const { items, isLoading: itemsLoading, fetchItems, createItem, updateItem, deleteItem } =
    useExtractionGroundTruthItems(nav.selectedSet?.id || null)

  const selectedSchema: ExtractionSchema | null =
    nav.selectedSet ? schemas.find((s) => s.id === nav.selectedSet.extractionSchemaId) || null : null

  const handleCreateSet = async (data: {
    extractionSchemaId: string
    name: string
    description?: string
  }) => {
    try {
      await createSet(data)
      toast.success('Ground truth set created')
    } catch (err) {
      toast.error('Failed to create set', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const handleDeleteSet = async (id: string) => {
    try {
      await deleteSet(id)
      if (nav.selectedSet?.id === id) {
        dispatch({ type: 'BACK_TO_LIST' })
      }
      toast.success('Ground truth set deleted')
    } catch (err) {
      toast.error('Failed to delete set', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const handleAddItem = useCallback(
    async (documentId: string) => {
      try {
        await createItem({ documentId, expectedData: {} })
        toast.success('Document added')
      } catch (err) {
        toast.error('Failed to add document', {
          description: err instanceof Error ? err.message : 'An error occurred',
        })
      }
    },
    [createItem]
  )

  const handleDeleteItem = useCallback(
    async (itemId: string) => {
      try {
        await deleteItem(itemId)
        toast.success('Item deleted')
      } catch (err) {
        toast.error('Failed to delete item', {
          description: err instanceof Error ? err.message : 'An error occurred',
        })
      }
    },
    [deleteItem]
  )

  const handleSaveItem = async (
    itemId: string,
    expectedData: Record<string, unknown>,
    annotations: Record<string, unknown> | null
  ) => {
    await updateItem(itemId, { expectedData, annotations: annotations ?? undefined })
    await fetchItems()
    await fetchSets()
  }

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage ground truth.
      </div>
    )
  }

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Extraction Ground Truth</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 min-h-0">
        {nav.view === 'editor' ? (
          <div className="flex-1">
            <GroundTruthEditor
              item={nav.editingItem}
              items={items}
              schema={selectedSchema}
              onSave={handleSaveItem}
              onBack={() => dispatch({ type: 'BACK_TO_DETAIL' })}
              onNavigate={(item) => dispatch({ type: 'NAVIGATE_ITEM', item })}
            />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-6 max-w-3xl">
            {nav.view === 'list' ? (
              <GroundTruthSetList
                sets={sets}
                schemas={schemas}
                isLoading={setsLoading}
                onSelect={(set) => dispatch({ type: 'SELECT_SET', set })}
                onCreate={handleCreateSet}
                onDelete={handleDeleteSet}
              />
            ) : (
              <GroundTruthSetDetail
                set={nav.selectedSet}
                items={items}
                documents={documents}
                isLoading={itemsLoading}
                onBack={() => dispatch({ type: 'BACK_TO_LIST' })}
                onAddItem={handleAddItem}
                onDeleteItem={handleDeleteItem}
                onEditItem={(item) => dispatch({ type: 'EDIT_ITEM', item })}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
