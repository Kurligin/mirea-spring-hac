import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Flex,
  Group,
  Menu,
  Paper,
  Progress,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import {
  IconCalendarEvent,
  IconCalendarOff,
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconHourglassHigh,
  IconPlayerPlay,
  IconPlus,
  IconQrcode,
  IconSearch,
} from '@tabler/icons-react'
import { useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { StatusBadge } from '../components/StatusBadge'
import { useState } from 'react'

interface Event {
  id: string
  title: string
  starts_at: string
  status: string
  capacity: number | null
  event_type: string
  custom_type_label: string | null
  duration_minutes: number
  confirmed_count: number | null
  waitlist_count: number | null
  registration_opens_at: string | null
}

const STATUS_FILTERS = [
  { value: 'all', label: 'Все' },
  { value: 'published', label: 'Опубликованы' },
  { value: 'draft', label: 'Черновики' },
  { value: 'cancelled', label: 'Отменены' },
]

const GROUP_OPTIONS = [
  { value: 'none', label: 'Без группировки' },
  { value: 'time', label: 'По времени' },
]

const DATE_FMT = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
})

const TYPE_LABELS: Record<string, string> = {
  open_day: 'День открытых дверей',
  master_class: 'Мастер-класс',
  olympiad: 'Олимпиада',
  consultation: 'Консультация',
  other: 'Мероприятие',
}

type SortField = 'title' | 'starts_at' | 'confirmed' | 'status'
type SortDir = 'asc' | 'desc'

const STATUS_PRIORITY: Record<string, number> = {
  published: 0,
  draft: 1,
  cancelled: 2,
}

const injectStyles = (() => {
  let done = false
  return () => {
    if (done) return
    done = true
    const s = document.createElement('style')
    s.textContent = `
      @keyframes events-fadeUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes events-skeleton {
        0%   { background-position: -400px 0; }
        100% { background-position: 400px 0; }
      }
      .events-skeleton-row {
        background: linear-gradient(90deg, #e2e8f0 0px, #f1f5f9 80px, #e2e8f0 160px);
        background-size: 400px 100%;
        animation: events-skeleton 1.4s infinite linear;
        border-radius: 6px;
      }
      .events-row {
        cursor: pointer;
        transition: background-color 0.12s ease;
      }
      .events-row:hover {
        background: var(--color-neutral-50) !important;
      }
      .events-th-sortable {
        cursor: pointer;
        user-select: none;
      }
      .events-th-sortable:hover {
        background: var(--color-neutral-50);
      }
    `
    document.head.appendChild(s)
  }
})()

export function EventsListPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const statusFilter = params.get('status') || 'all'
  const filter = params.get('q') || ''
  const sortField = (params.get('sort') as SortField | null) || 'starts_at'
  const sortDir = (params.get('dir') as SortDir | null) || 'asc'
  const grouping = params.get('group') || 'none'

  const [events, setEvents] = useState<Event[] | null>(null)

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === '') next.delete(k)
      else next.set(k, v)
    }
    setParams(next, { replace: true })
  }

  useEffect(() => {
    injectStyles()
    const qs = statusFilter === 'all' ? '?limit=200' : `?status=${statusFilter}&limit=200`
    api.get<Event[]>(`/api/admin/events${qs}`).then((r) => setEvents(r.data))
  }, [statusFilter])

  const filtered = useMemo(() => {
    const arr = events?.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase())) ?? []
    const sign = sortDir === 'asc' ? 1 : -1
    return [...arr].sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case 'title':
          cmp = a.title.localeCompare(b.title, 'ru')
          break
        case 'confirmed':
          cmp = (a.confirmed_count ?? 0) - (b.confirmed_count ?? 0)
          break
        case 'status':
          cmp = (STATUS_PRIORITY[a.status] ?? 99) - (STATUS_PRIORITY[b.status] ?? 99)
          break
        case 'starts_at':
        default:
          cmp = new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
      }
      return cmp * sign
    })
  }, [events, filter, sortField, sortDir])

  function toggleSort(field: SortField) {
    if (sortField === field) {
      update({ dir: sortDir === 'asc' ? 'desc' : 'asc' })
    } else {
      update({ sort: field, dir: field === 'starts_at' || field === 'title' ? 'asc' : 'desc' })
    }
  }

  function SortableTh({ field, label, style }: { field: SortField; label: string; style?: React.CSSProperties }) {
    const active = sortField === field
    return (
      <Table.Th
        className="events-th-sortable"
        style={style}
        onClick={() => toggleSort(field)}
      >
        <Flex align="center" gap={4}>
          <Text fz="sm" fw={600} c={active ? 'brand' : undefined}>{label}</Text>
          {active && (sortDir === 'asc' ? <IconChevronUp size={14} stroke={2.2} /> : <IconChevronDown size={14} stroke={2.2} />)}
        </Flex>
      </Table.Th>
    )
  }

  const groups = useMemo(() => groupByTime(filtered), [filtered])

  return (
    <Stack gap="lg" style={{ animation: 'events-fadeUp 0.35s ease both' }}>
      {/* Header */}
      <Group justify="space-between" align="flex-end">
        <Stack gap={4}>
          <Title order={2} style={{ color: '#0f172a' }}>
            Мероприятия
          </Title>
          <Text c="dimmed" fz="sm">
            {events ? `${events.length} всего` : 'Загрузка…'}
          </Text>
        </Stack>
        <Menu position="bottom-end" shadow="md" width={260}>
          <Menu.Target>
            <Button
              leftSection={<IconPlus size={18} stroke={2} />}
              size="md"
              style={{ background: 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)' }}
            >
              Создать
            </Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Label>Из шаблона</Menu.Label>
            <Menu.Item onClick={() => navigate('new?template=open_day')}>
              День открытых дверей
            </Menu.Item>
            <Menu.Item onClick={() => navigate('new?template=master_class')}>
              Мастер-класс
            </Menu.Item>
            <Menu.Item onClick={() => navigate('new?template=olympiad')}>
              Олимпиада
            </Menu.Item>
            <Menu.Item onClick={() => navigate('new?template=consultation')}>
              Консультация
            </Menu.Item>
            <Menu.Divider />
            <Menu.Item onClick={() => navigate('new')}>
              Пустое мероприятие
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>

      {/* Filters bar */}
      <Flex gap="md" wrap="wrap" align="center">
        <TextInput
          placeholder="Поиск по названию"
          value={filter}
          onChange={(e) => update({ q: e.currentTarget.value || null })}
          leftSection={<IconSearch size={16} stroke={1.8} />}
          w={320}
        />
        <SegmentedControl
          value={statusFilter}
          onChange={(v) => update({ status: v === 'all' ? null : v })}
          data={STATUS_FILTERS}
        />
        <SegmentedControl
          value={grouping}
          onChange={(v) => update({ group: v === 'none' ? null : v })}
          data={GROUP_OPTIONS}
          size="sm"
        />
      </Flex>

      {/* Main content */}
      <Paper withBorder radius="lg" style={{ overflow: 'hidden' }}>
        {!events ? (
          <Stack gap={0}>
            {Array.from({ length: 4 }).map((_, i) => (
              <Box
                key={i}
                p="md"
                style={{ borderBottom: '1px solid var(--color-neutral-100)' }}
              >
                <Flex justify="space-between" align="center" gap="md">
                  <Box className="events-skeleton-row" style={{ flex: 1, height: 18 }} />
                  <Box
                    className="events-skeleton-row"
                    style={{ width: 120, height: 18 }}
                  />
                  <Box
                    className="events-skeleton-row"
                    style={{ width: 80, height: 22, borderRadius: 11 }}
                  />
                </Flex>
              </Box>
            ))}
          </Stack>
        ) : filtered.length === 0 ? (
          <Stack align="center" gap="md" py={64} px="md">
            <Box
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: 'rgba(44,84,238,0.08)',
                color: '#2c54ee',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <IconCalendarOff size={36} stroke={1.6} />
            </Box>
            <Stack gap={4} align="center">
              <Title order={4} style={{ color: '#0f172a' }}>
                {filter ? 'Ничего не найдено' : 'Пока нет мероприятий'}
              </Title>
              <Text c="dimmed" ta="center" fz="sm" style={{ maxWidth: 320 }}>
                {filter
                  ? 'Попробуйте изменить запрос или сбросить фильтры'
                  : 'Создайте первое мероприятие — оно появится здесь.'}
              </Text>
            </Stack>
            {!filter && (
              <Button
                leftSection={<IconPlus size={16} stroke={2} />}
                onClick={() => navigate('new')}
                mt="sm"
              >
                Создать первое
              </Button>
            )}
          </Stack>
        ) : (
          <Table verticalSpacing="md" horizontalSpacing="lg">
            <Table.Thead>
              <Table.Tr>
                <SortableTh field="title" label="Название" />
                <SortableTh field="starts_at" label="Дата" />
                <SortableTh field="confirmed" label="Записи" style={{ minWidth: 180 }} />
                <SortableTh field="status" label="Статус" />
                <Table.Th style={{ width: 40 }} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {grouping === 'time'
                ? groups.flatMap((g) =>
                    g.items.length === 0 ? [] : [
                      <Table.Tr key={`hdr-${g.key}`} style={{ background: 'var(--color-neutral-50)' }}>
                        <Table.Td colSpan={5} style={{ padding: '8px 16px' }}>
                          <Text fz="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: 0.6 }}>
                            {g.label} · {g.items.length}
                          </Text>
                        </Table.Td>
                      </Table.Tr>,
                      ...g.items.map((e) => renderRow(e, navigate)),
                    ],
                  )
                : filtered.map((e) => renderRow(e, navigate))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
    </Stack>
  )
}

function renderRow(e: Event, navigate: (to: string) => void) {
  return (
    <Table.Tr
      key={e.id}
      className="events-row"
      onClick={() => navigate(e.id)}
    >
      <Table.Td>
        <Flex align="center" gap="sm">
          <Box
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'rgba(44,84,238,0.08)',
              color: '#2c54ee',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <IconCalendarEvent size={20} stroke={1.8} />
          </Box>
          <Stack gap={4}>
            <Flex align="center" gap={6} wrap="wrap">
              <Text fw={600} style={{ color: '#0f172a' }}>
                {e.title}
              </Text>
              <RowStatusBadges event={e} />
            </Flex>
            <Text fz="xs" c="dimmed">
              {e.event_type === 'other' && e.custom_type_label
                ? e.custom_type_label
                : (TYPE_LABELS[e.event_type] ?? e.event_type)}
            </Text>
          </Stack>
        </Flex>
      </Table.Td>
      <Table.Td>
        <Text fz="sm" style={{ color: '#334155' }}>
          {DATE_FMT.format(new Date(e.starts_at))}
        </Text>
        <Text fz="xs" c="dimmed">
          {e.duration_minutes} мин
        </Text>
      </Table.Td>
      <Table.Td>
        <CapacityCell event={e} />
      </Table.Td>
      <Table.Td>
        <StatusBadge status={e.status} />
      </Table.Td>
      <Table.Td onClick={(ev) => ev.stopPropagation()}>
        <Group gap={4} wrap="nowrap" justify="flex-end">
          <ActionIcon
            variant="subtle"
            color="teal"
            title="Контроль входа"
            onClick={() => navigate(`${e.id}/checkin`)}
          >
            <IconQrcode size={18} stroke={1.8} />
          </ActionIcon>
          <ActionIcon variant="subtle" color="gray" onClick={() => navigate(e.id)}>
            <IconChevronRight size={18} stroke={1.8} />
          </ActionIcon>
        </Group>
      </Table.Td>
    </Table.Tr>
  )
}

function groupByTime(events: Event[]): { key: string; label: string; items: Event[] }[] {
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const endOfToday = startOfToday + 86_400_000
  const endOfWeek = startOfToday + 7 * 86_400_000

  const today: Event[] = []
  const week: Event[] = []
  const future: Event[] = []
  const past: Event[] = []
  for (const e of events) {
    const ts = new Date(e.starts_at).getTime()
    if (ts < startOfToday) past.push(e)
    else if (ts < endOfToday) today.push(e)
    else if (ts < endOfWeek) week.push(e)
    else future.push(e)
  }
  return [
    { key: 'today', label: 'Сегодня', items: today },
    { key: 'week', label: 'Эта неделя', items: week },
    { key: 'future', label: 'Дальше', items: future },
    { key: 'past', label: 'Прошедшие', items: past },
  ]
}

function CapacityCell({ event }: { event: Event }) {
  const confirmed = event.confirmed_count ?? 0
  const cap = event.capacity
  if (!cap) {
    return (
      <Stack gap={2}>
        <Text fz="sm" fw={600} style={{ color: '#334155', fontVariantNumeric: 'tabular-nums' }}>
          {confirmed} <Text component="span" c="dimmed" fz="xs">записей · ∞</Text>
        </Text>
        {(event.waitlist_count ?? 0) > 0 && (
          <Text fz="xs" c="dimmed">+{event.waitlist_count} в листе ожидания</Text>
        )}
      </Stack>
    )
  }
  const pct = Math.min(100, Math.round((confirmed / cap) * 100))
  const color = pct >= 100 ? 'red' : pct >= 80 ? 'orange' : 'brand'
  return (
    <Stack gap={4} style={{ minWidth: 160 }}>
      <Flex justify="space-between" gap="xs">
        <Text fz="sm" fw={600} style={{ color: '#334155', fontVariantNumeric: 'tabular-nums' }}>
          {confirmed} / {cap}
        </Text>
        <Text fz="xs" c="dimmed" style={{ fontVariantNumeric: 'tabular-nums' }}>{pct}%</Text>
      </Flex>
      <Progress value={pct} color={color} size="sm" radius="xl" />
      {(event.waitlist_count ?? 0) > 0 && (
        <Text fz="xs" c="dimmed">+{event.waitlist_count} в листе ожидания</Text>
      )}
    </Stack>
  )
}

function RowStatusBadges({ event }: { event: Event }) {
  const now = Date.now()
  const startsAt = new Date(event.starts_at).getTime()
  const endsAt = startsAt + event.duration_minutes * 60_000
  const opensAt = event.registration_opens_at ? new Date(event.registration_opens_at).getTime() : null

  const isLive = event.status === 'published' && startsAt <= now && now < endsAt
  const isUpcomingSoon =
    opensAt !== null && now < opensAt && opensAt - now < 7 * 24 * 3600_000

  if (isLive) {
    return (
      <Badge color="red" variant="light" leftSection={<IconPlayerPlay size={10} stroke={2.4} />}>
        идёт сейчас
      </Badge>
    )
  }
  if (isUpcomingSoon) {
    return (
      <Badge color="orange" variant="light" leftSection={<IconHourglassHigh size={10} stroke={2.4} />}>
        регистрация скоро откроется
      </Badge>
    )
  }
  return null
}
