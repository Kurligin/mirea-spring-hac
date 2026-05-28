import { ActionIcon, Badge, Box, Button, Flex, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { StatusBadge } from '../components/StatusBadge'

interface Event {
  id: string
  title: string
  starts_at: string
  duration_minutes: number
  status: string
  location: string | null
  event_type: string
  custom_type_label: string | null
}

const WEEK_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const MONTH_LABELS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

const TIME_FMT = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function startOfMonthGrid(year: number, month: number): Date {
  const first = new Date(year, month, 1)
  // Week starts Monday: shift so Monday=0
  const dayOfWeekMon0 = (first.getDay() + 6) % 7
  const start = new Date(year, month, 1 - dayOfWeekMon0)
  start.setHours(0, 0, 0, 0)
  return start
}

export function CalendarPage() {
  const navigate = useNavigate()
  const [events, setEvents] = useState<Event[] | null>(null)

  const today = useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])

  const [cursor, setCursor] = useState<{ year: number; month: number }>(() => ({
    year: today.getFullYear(),
    month: today.getMonth(),
  }))
  const [selected, setSelected] = useState<string>(ymd(today))

  useEffect(() => {
    api.get<Event[]>('/api/admin/events?limit=500')
      .then((r) => setEvents(r.data))
      .catch(() => setEvents([]))
  }, [])

  const byDate = useMemo(() => {
    const map = new Map<string, Event[]>()
    if (!events) return map
    for (const e of events) {
      const key = ymd(new Date(e.starts_at))
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(e)
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
    }
    return map
  }, [events])

  const gridStart = useMemo(() => startOfMonthGrid(cursor.year, cursor.month), [cursor.year, cursor.month])
  const cells = useMemo(() => {
    const arr: Date[] = []
    for (let i = 0; i < 42; i++) {
      const d = new Date(gridStart)
      d.setDate(gridStart.getDate() + i)
      arr.push(d)
    }
    return arr
  }, [gridStart])

  function prev() {
    setCursor((c) => {
      const m = c.month - 1
      if (m < 0) return { year: c.year - 1, month: 11 }
      return { year: c.year, month: m }
    })
  }
  function next() {
    setCursor((c) => {
      const m = c.month + 1
      if (m > 11) return { year: c.year + 1, month: 0 }
      return { year: c.year, month: m }
    })
  }
  function goToday() {
    setCursor({ year: today.getFullYear(), month: today.getMonth() })
    setSelected(ymd(today))
  }

  const selectedEvents = byDate.get(selected) ?? []
  const selectedDate = useMemo(() => {
    const [y, m, d] = selected.split('-').map(Number)
    return new Date(y, m - 1, d)
  }, [selected])

  return (
    <Stack gap="lg">
      <Flex justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <Stack gap={4}>
          <Title order={2} style={{ color: '#0f172a' }}>Календарь</Title>
          <Text c="dimmed" fz="sm">Все мероприятия по датам</Text>
        </Stack>
        <Group>
          <Button variant="default" size="sm" onClick={goToday}>Сегодня</Button>
        </Group>
      </Flex>

      <Flex gap="lg" align="flex-start" wrap="wrap">
        {/* Сетка месяца */}
        <Paper withBorder radius="lg" p="lg" style={{ flex: '1 1 600px', minWidth: 480 }}>
          <Flex justify="space-between" align="center" mb="md">
            <Group gap="xs">
              <ActionIcon variant="subtle" onClick={prev} aria-label="Предыдущий месяц">
                <IconChevronLeft size={20} />
              </ActionIcon>
              <Title order={4} style={{ color: '#0f172a', minWidth: 180 }}>
                {MONTH_LABELS[cursor.month]} {cursor.year}
              </Title>
              <ActionIcon variant="subtle" onClick={next} aria-label="Следующий месяц">
                <IconChevronRight size={20} />
              </ActionIcon>
            </Group>
          </Flex>

          {events === null ? (
            <Flex justify="center" py="xl"><Loader /></Flex>
          ) : (
            <Box>
              <Box style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
                {WEEK_LABELS.map((w) => (
                  <Text key={w} fz="xs" fw={600} c="dimmed" tt="uppercase" ta="center" py={6}>
                    {w}
                  </Text>
                ))}
                {cells.map((d) => {
                  const key = ymd(d)
                  const inMonth = d.getMonth() === cursor.month
                  const isToday = d.getTime() === today.getTime()
                  const isSelected = key === selected
                  const dayEvents = byDate.get(key) ?? []
                  const count = dayEvents.length
                  return (
                    <Box
                      key={key}
                      onClick={() => setSelected(key)}
                      style={{
                        position: 'relative',
                        cursor: 'pointer',
                        background: isSelected
                          ? 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)'
                          : isToday
                            ? 'rgba(44,84,238,0.08)'
                            : 'transparent',
                        color: isSelected ? '#fff' : inMonth ? '#0f172a' : '#94a3b8',
                        borderRadius: 10,
                        padding: '10px 6px 22px',
                        minHeight: 64,
                        transition: 'background 0.12s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) e.currentTarget.style.background = 'var(--color-neutral-50)'
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.background = isToday
                            ? 'rgba(44,84,238,0.08)'
                            : 'transparent'
                        }
                      }}
                    >
                      <Text fz="md" fw={isToday || isSelected ? 700 : 500} ta="center">
                        {d.getDate()}
                      </Text>
                      {count > 0 && (
                        <Box
                          style={{
                            position: 'absolute',
                            bottom: 6,
                            left: '50%',
                            transform: 'translateX(-50%)',
                            background: isSelected ? 'rgba(255,255,255,0.25)' : '#2c54ee',
                            color: '#fff',
                            borderRadius: 9999,
                            fontSize: 10,
                            fontWeight: 700,
                            minWidth: 18,
                            height: 18,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '0 5px',
                          }}
                        >
                          {count}
                        </Box>
                      )}
                    </Box>
                  )
                })}
              </Box>
            </Box>
          )}
        </Paper>

        {/* Правая панель — события выбранного дня */}
        <Paper withBorder radius="lg" p="lg" style={{ flex: '1 1 380px', minWidth: 320 }}>
          <Stack gap="md">
            <Stack gap={2}>
              <Text fz="xs" c="dimmed" tt="uppercase" fw={600}>
                {WEEK_LABELS[(selectedDate.getDay() + 6) % 7]}
              </Text>
              <Title order={3} style={{ color: '#0f172a' }}>
                {selectedDate.getDate()} {MONTH_LABELS[selectedDate.getMonth()].toLowerCase()}
              </Title>
              <Text c="dimmed" fz="sm">
                {selectedEvents.length > 0
                  ? `${selectedEvents.length} ${plural(selectedEvents.length, ['мероприятие', 'мероприятия', 'мероприятий'])}`
                  : 'Нет мероприятий'}
              </Text>
            </Stack>

            {selectedEvents.map((e) => (
              <Box
                key={e.id}
                onClick={() => navigate(`/events/${e.id}`)}
                style={{
                  cursor: 'pointer',
                  padding: '12px 14px',
                  borderRadius: 12,
                  border: '1px solid var(--color-neutral-200)',
                  background: 'rgba(255,255,255,0.7)',
                  transition: 'background 0.12s ease',
                }}
                onMouseEnter={(ev) => ev.currentTarget.style.background = 'var(--color-neutral-50)'}
                onMouseLeave={(ev) => ev.currentTarget.style.background = 'rgba(255,255,255,0.7)'}
              >
                <Flex justify="space-between" align="center" gap="sm" mb={4}>
                  <Badge variant="light" color="brand" size="sm">
                    {TIME_FMT.format(new Date(e.starts_at))}
                  </Badge>
                  <StatusBadge status={e.status} />
                </Flex>
                <Text fw={600} style={{ color: '#0f172a', lineHeight: 1.3 }}>
                  {e.title}
                </Text>
                <Text fz="xs" c="dimmed" mt={2}>
                  {e.event_type === 'other' && e.custom_type_label ? e.custom_type_label : ''}
                  {e.location ? ` · ${e.location}` : ''}
                </Text>
              </Box>
            ))}
          </Stack>
        </Paper>
      </Flex>
    </Stack>
  )
}

function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100
  const b = a % 10
  if (a > 10 && a < 20) return forms[2]
  if (b > 1 && b < 5) return forms[1]
  if (b === 1) return forms[0]
  return forms[2]
}
