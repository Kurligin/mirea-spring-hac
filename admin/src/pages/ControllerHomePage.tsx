import { Alert, Badge, Box, Flex, Stack, Text, TextInput, Title } from '@mantine/core'
import { IconArrowRight, IconCalendarEvent, IconHourglassHigh, IconPlayerPlay, IconSearch } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'

interface MyEvent {
  id: string
  title: string
  starts_at: string
  location: string | null
  duration_minutes?: number
}

const DATE_FMT = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
})

function timeBadge(event: MyEvent): { label: string; color: string; icon: 'play' | 'hourglass' | 'calendar' } {
  const now = Date.now()
  const startsAt = new Date(event.starts_at).getTime()
  const endsAt = startsAt + (event.duration_minutes ?? 60) * 60_000
  if (startsAt <= now && now < endsAt) {
    return { label: 'идёт сейчас', color: 'red', icon: 'play' }
  }
  const diff = startsAt - now
  if (diff < 15 * 60_000) return { label: 'через несколько минут', color: 'orange', icon: 'hourglass' }
  if (diff < 60 * 60_000) {
    const m = Math.round(diff / 60_000)
    return { label: `через ${m} мин`, color: 'orange', icon: 'hourglass' }
  }
  if (diff < 24 * 3600_000) {
    const h = Math.round(diff / 3600_000)
    return { label: `через ${h} ч`, color: 'blue', icon: 'hourglass' }
  }
  if (diff < 48 * 3600_000) return { label: 'завтра', color: 'blue', icon: 'calendar' }
  const days = Math.round(diff / 86_400_000)
  return { label: `через ${days} дн`, color: 'gray', icon: 'calendar' }
}

function BadgeIcon({ icon }: { icon: 'play' | 'hourglass' | 'calendar' }) {
  if (icon === 'play') return <IconPlayerPlay size={12} stroke={2.4} />
  if (icon === 'hourglass') return <IconHourglassHigh size={12} stroke={2.2} />
  return <IconCalendarEvent size={12} stroke={2.2} />
}

export function ControllerHomePage() {
  const [events, setEvents] = useState<MyEvent[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    api
      .get<MyEvent[]>('/api/admin/controller/my-events')
      .then((r) => setEvents(r.data))
      .catch(() => setErr('Не удалось загрузить список мероприятий.'))
  }, [])

  // Сортировка + фильтрация по поиску
  const filtered = useMemo(() => {
    if (!events) return null
    const q = query.trim().toLowerCase()
    const arr = q
      ? events.filter((e) =>
          e.title.toLowerCase().includes(q) ||
          (e.location ?? '').toLowerCase().includes(q),
        )
      : [...events]
    return arr.sort((a, b) => {
      const now = Date.now()
      const aStart = new Date(a.starts_at).getTime()
      const bStart = new Date(b.starts_at).getTime()
      const aLive = aStart <= now && now < aStart + (a.duration_minutes ?? 60) * 60_000
      const bLive = bStart <= now && now < bStart + (b.duration_minutes ?? 60) * 60_000
      if (aLive !== bLive) return aLive ? -1 : 1
      return Math.abs(aStart - now) - Math.abs(bStart - now)
    })
  }, [events, query])

  if (err) return <Alert color="red">{err}</Alert>
  if (events === null) return <Text c="dimmed">Загрузка…</Text>
  if (events.length === 0) {
    return (
      <Stack gap="md" align="center" py="xl">
        <Title order={3}>Нет назначенных мероприятий</Title>
        <Text c="dimmed">Свяжитесь с организатором.</Text>
      </Stack>
    )
  }

  return (
    <Stack gap="md">
      <Stack gap={4}>
        <Title order={2} style={{ color: '#0f172a' }}>Выберите мероприятие</Title>
        <Text c="dimmed" fz="sm">
          Назначено: {events.length}. Откройте то, где будете проверять вход.
        </Text>
      </Stack>

      {events.length > 3 && (
        <TextInput
          placeholder="Поиск по названию или месту"
          leftSection={<IconSearch size={16} stroke={1.8} />}
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          size="md"
        />
      )}

      <Stack gap="sm">
        {filtered && filtered.length === 0 && (
          <Text c="dimmed" ta="center" py="md">Ничего не найдено</Text>
        )}
        {filtered?.map((e) => {
          const t = timeBadge(e)
          return (
            <Box
              key={e.id}
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/events/${e.id}/checkin`)}
              onKeyDown={(ev) => {
                if (ev.key === 'Enter' || ev.key === ' ') {
                  ev.preventDefault()
                  navigate(`/events/${e.id}/checkin`)
                }
              }}
              style={{
                position: 'relative',
                borderRadius: 16,
                padding: '1rem 1.25rem',
                paddingRight: '3rem',
                background: t.color === 'red'
                  ? 'linear-gradient(135deg, #fee2e2 0%, #fff 60%)'
                  : '#fff',
                border: `1px solid ${t.color === 'red' ? '#fecaca' : 'var(--color-neutral-200)'}`,
                cursor: 'pointer',
                transition: 'transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease',
                boxShadow: '0 2px 6px rgba(15,23,42,0.04)',
              }}
              onMouseEnter={(ev) => {
                ev.currentTarget.style.transform = 'translateY(-1px)'
                ev.currentTarget.style.boxShadow = '0 10px 22px rgba(15,23,42,0.08)'
                ev.currentTarget.style.borderColor = '#2c54ee'
              }}
              onMouseLeave={(ev) => {
                ev.currentTarget.style.transform = 'translateY(0)'
                ev.currentTarget.style.boxShadow = '0 2px 6px rgba(15,23,42,0.04)'
                ev.currentTarget.style.borderColor =
                  t.color === 'red' ? '#fecaca' : 'var(--color-neutral-200)'
              }}
            >
              <Stack gap={6} style={{ minWidth: 0 }}>
                <Flex align="center" gap="xs" wrap="wrap">
                  <Badge
                    color={t.color}
                    variant={t.color === 'red' ? 'filled' : 'light'}
                    leftSection={<BadgeIcon icon={t.icon} />}
                    size="md"
                  >
                    {t.label}
                  </Badge>
                </Flex>
                <Text fw={600} fz="lg" style={{ color: '#0f172a', lineHeight: 1.3 }}>
                  {e.title}
                </Text>
                <Text c="dimmed" fz="sm">
                  {DATE_FMT.format(new Date(e.starts_at))}
                  {e.location ? ` · ${e.location}` : ''}
                </Text>
              </Stack>
              <Box
                style={{
                  position: 'absolute',
                  right: 14,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: t.color === 'red' ? '#dc2626' : 'rgba(44,84,238,0.12)',
                  color: t.color === 'red' ? '#fff' : '#2c54ee',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <IconArrowRight size={18} stroke={2.2} />
              </Box>
            </Box>
          )
        })}
      </Stack>
    </Stack>
  )
}
