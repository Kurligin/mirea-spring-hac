import {
  Badge, Box, Code, Flex, Loader, Paper, Select, Stack, Table, Text, TextInput, Title,
} from '@mantine/core'
import { IconShieldLock } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { useAuthStore } from '../stores/auth'

interface AuditEntry {
  id: string
  actor_kind: string
  actor_id: string | null
  actor_email: string | null
  action: string
  target_kind: string | null
  target_id: string | null
  payload: Record<string, unknown> | null
  created_at: string
}

const ACTION_LABELS: Record<string, string> = {
  'event.publish': 'Опубликовано мероприятие',
  'event.cancel': 'Отменено мероприятие',
  'event.restore': 'Восстановлено мероприятие',
  'event.delete': 'Удалено мероприятие',
  'admin.create': 'Создан аккаунт',
}

const ACTION_COLORS: Record<string, string> = {
  'event.publish': 'teal',
  'event.cancel': 'red',
  'event.restore': 'blue',
  'event.delete': 'red',
  'admin.create': 'orange',
}

const DATE_FMT = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit', month: '2-digit', year: 'numeric',
  hour: '2-digit', minute: '2-digit', second: '2-digit',
})

const ACTION_OPTIONS = [
  { value: '', label: 'Все действия' },
  ...Object.entries(ACTION_LABELS).map(([k, v]) => ({ value: k, label: v })),
]

export function AuditPage() {
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.profile?.role)
  const [actionFilter, setActionFilter] = useState('')
  const [search, setSearch] = useState('')

  if (role && role !== 'super') {
    return (
      <Stack align="center" gap="md" py="xl">
        <IconShieldLock size={48} stroke={1.5} color="#94a3b8" />
        <Title order={4} c="dimmed">Доступ только для super-админа</Title>
      </Stack>
    )
  }

  const q = useQuery({
    queryKey: ['audit', actionFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: '500' })
      if (actionFilter) params.set('action', actionFilter)
      return (await api.get<AuditEntry[]>(`/api/admin/audit?${params.toString()}`)).data
    },
  })

  const filtered = (q.data ?? []).filter((e) => {
    if (!search.trim()) return true
    const needle = search.toLowerCase()
    return (
      e.actor_email?.toLowerCase().includes(needle) ||
      e.action.toLowerCase().includes(needle) ||
      JSON.stringify(e.payload ?? {}).toLowerCase().includes(needle)
    )
  })

  return (
    <Stack gap="lg">
      <Stack gap={4}>
        <Title order={2} style={{ color: '#0f172a' }}>Журнал действий</Title>
        <Text c="dimmed" fz="sm">Кто, что и когда менял. Видно только super-админу.</Text>
      </Stack>

      <Flex gap="md" wrap="wrap">
        <Select
          data={ACTION_OPTIONS}
          value={actionFilter || null}
          onChange={(v) => setActionFilter(v || '')}
          placeholder="Тип действия"
          clearable
          w={260}
        />
        <TextInput
          placeholder="Поиск: email админа, payload"
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          w={280}
        />
      </Flex>

      <Paper withBorder radius="lg" style={{ overflow: 'hidden' }}>
        {q.isLoading ? (
          <Flex justify="center" py="xl"><Loader /></Flex>
        ) : filtered.length === 0 ? (
          <Stack align="center" gap="xs" py="xl">
            <Text c="dimmed">Нет событий по выбранным фильтрам</Text>
          </Stack>
        ) : (
          <Table verticalSpacing="sm" horizontalSpacing="lg" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Когда</Table.Th>
                <Table.Th>Кто</Table.Th>
                <Table.Th>Действие</Table.Th>
                <Table.Th>Цель</Table.Th>
                <Table.Th>Детали</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtered.map((e) => (
                <Table.Tr
                  key={e.id}
                  style={{
                    cursor: e.target_kind === 'event' && e.target_id ? 'pointer' : 'default',
                  }}
                  onClick={() => {
                    if (e.target_kind === 'event' && e.target_id) {
                      navigate(`/events/${e.target_id}`)
                    }
                  }}
                >
                  <Table.Td>
                    <Text fz="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                      {DATE_FMT.format(new Date(e.created_at))}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text fz="sm">{e.actor_email || e.actor_kind}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={ACTION_COLORS[e.action] ?? 'gray'} variant="light">
                      {ACTION_LABELS[e.action] ?? e.action}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text fz="xs" c="dimmed">
                      {e.target_kind ?? '—'}
                      {e.target_id ? ` · ${e.target_id.slice(0, 8)}` : ''}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ maxWidth: 360 }}>
                    {e.payload && Object.keys(e.payload).length > 0 ? (
                      <Code fz="xs" style={{ whiteSpace: 'pre-wrap', display: 'block' }}>
                        {Object.entries(e.payload)
                          .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
                          .join('  ·  ')}
                      </Code>
                    ) : (
                      <Text fz="xs" c="dimmed">—</Text>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
      <Box />
    </Stack>
  )
}
