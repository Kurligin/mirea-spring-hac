import { Badge } from '@mantine/core'

const MAP: Record<string, { color: string; label: string }> = {
  pending:   { color: 'gray',   label: 'Ожидает модерации' },
  confirmed: { color: 'teal',   label: 'Подтверждено' },
  waitlist:  { color: 'orange', label: 'Лист ожидания' },
  cancelled: { color: 'red',    label: 'Отменено' },
  rejected:  { color: 'dark',   label: 'Отклонено' },
}

export function RegistrationStatusBadge({ status }: { status: string }) {
  const meta = MAP[status] ?? { color: 'gray', label: status }
  return <Badge color={meta.color} variant="light" radius="sm">{meta.label}</Badge>
}
