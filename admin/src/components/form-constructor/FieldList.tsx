import {
  closestCenter, DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ActionIcon, Badge, Box, Flex, Group, Paper, Stack, Text } from '@mantine/core'
import { IconGripVertical, IconPencil, IconTrash } from '@tabler/icons-react'

import { FIELD_TYPE_META, FieldDraft } from './types'

function Row({ field, onEdit, onRemove }: { field: FieldDraft; onEdit: () => void; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: field.key,
  })
  return (
    <Paper
      ref={setNodeRef}
      withBorder
      radius="md"
      p="sm"
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        background: isDragging ? 'var(--color-brand-50)' : 'white',
      }}
    >
      <Flex justify="space-between" align="center" gap="sm">
        <Flex align="center" gap="sm" style={{ minWidth: 0, flex: 1 }}>
          <Box {...attributes} {...listeners} style={{ cursor: 'grab', color: '#94a3b8', flexShrink: 0 }}>
            <IconGripVertical size={18} stroke={1.6} />
          </Box>
          <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
            <Text fw={600} truncate style={{ color: '#0f172a' }}>{field.label || field.key}</Text>
            <Group gap={6}>
              <Badge size="xs" variant="light" color="brand">
                {FIELD_TYPE_META[field.field_type].label}
              </Badge>
              {field.required && (
                <Badge size="xs" variant="light" color="red">обязательное</Badge>
              )}
            </Group>
          </Stack>
        </Flex>
        <Group gap={4}>
          <ActionIcon variant="subtle" onClick={onEdit} aria-label="Редактировать">
            <IconPencil size={16} stroke={1.8} />
          </ActionIcon>
          <ActionIcon variant="subtle" color="red" onClick={onRemove} aria-label="Удалить">
            <IconTrash size={16} stroke={1.8} />
          </ActionIcon>
        </Group>
      </Flex>
    </Paper>
  )
}

export function FieldList({
  fields, onChange, onEdit,
}: {
  fields: FieldDraft[]
  onChange: (next: FieldDraft[]) => void
  onEdit: (idx: number) => void
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  function handleDragEnd(e: DragEndEvent) {
    const { active, over } = e
    if (over && active.id !== over.id) {
      const oldIdx = fields.findIndex((f) => f.key === active.id)
      const newIdx = fields.findIndex((f) => f.key === over.id)
      onChange(arrayMove(fields, oldIdx, newIdx).map((f, i) => ({ ...f, order: i })))
    }
  }
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={fields.map((f) => f.key)} strategy={verticalListSortingStrategy}>
        <Stack gap="xs">
          {fields.map((f, i) => (
            <Row
              key={f.key}
              field={f}
              onEdit={() => onEdit(i)}
              onRemove={() => onChange(fields.filter((_, j) => j !== i))}
            />
          ))}
        </Stack>
      </SortableContext>
    </DndContext>
  )
}
