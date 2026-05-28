import { Badge } from '@mantine/core'

const MAP: Record<string, { color: string; label: string }> = {
  draft: { color: 'gray', label: 'Черновик' },
  published: { color: 'teal', label: 'Опубликовано' },
  cancelled: { color: 'red', label: 'Отменено' },
  archived: { color: 'dark', label: 'Архив' },
}

export function StatusBadge({ status }: { status: string }) {
  const meta = MAP[status] ?? { color: 'gray', label: status }
  return (
    <Badge color={meta.color} variant="light" radius="sm">
      {meta.label}
    </Badge>
  )
}
