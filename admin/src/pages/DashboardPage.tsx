import { Box, Flex, Paper, SegmentedControl, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import type { Icon } from '@tabler/icons-react'
import {
  IconAlertTriangle,
  IconCalendarEvent,
  IconCircleCheck,
  IconHourglassHigh,
  IconInbox,
  IconUser,
  IconX,
} from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { api } from '../api'

interface Stats {
  upcoming_events: number
  confirmed_total: number
  waitlist_total: number
  cancelled_week: number
  active_users: number
  confirmed_week?: number
  confirmed_prev_week?: number
  cancelled_prev_week?: number
  upcoming_prev_week?: number
  active_users_prev_week?: number
}

interface TimeseriesPoint {
  date: string
  confirmed: number
  cancelled: number
  waitlist: number
}

interface FunnelData {
  event_view: number
  form_start: number
  confirm: number
}

const injectDashboardStyles = (() => {
  let done = false
  return () => {
    if (done) return
    done = true
    const s = document.createElement('style')
    s.textContent = `
      @keyframes dash-fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes dash-countUp {
        from { opacity: 0; transform: scale(0.8); }
        to   { opacity: 1; transform: scale(1); }
      }
      @keyframes dash-spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
      }
      @keyframes dash-skeletonShimmer {
        0%   { background-position: -400px 0; }
        100% { background-position: 400px 0; }
      }

      .dash-stat-card {
        position: relative;
        overflow: hidden;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        cursor: default;
      }
      .dash-stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -6px rgba(15,23,42,0.12),
                    0 4px 8px -4px rgba(0,0,0,0.06) !important;
      }

      .dash-skeleton {
        background: linear-gradient(
          90deg,
          #e2e8f0 0px,
          #f1f5f9 80px,
          #e2e8f0 160px
        );
        background-size: 400px 100%;
        animation: dash-skeletonShimmer 1.4s infinite linear;
        border-radius: 8px;
      }

      .dash-trend-up   { color: #16a34a; }
      .dash-trend-down { color: #dc2626; }
      .dash-trend-flat { color: #94a3b8; }
    `
    document.head.appendChild(s)
  }
})()

interface TileConfig {
  key: keyof Stats
  label: string
  Icon: Icon
  accent: string
  bg: string
  iconBg: string
  iconColor: string
}

interface Trend {
  dir: 'up' | 'down' | 'flat'
  pct: string
  label: string
}

function pctChange(now: number, prev: number): string {
  if (prev === 0) return now > 0 ? `+${now}` : '±0'
  const delta = ((now - prev) / prev) * 100
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : '±'
  return `${sign}${Math.abs(Math.round(delta))}%`
}

function computeTrend(key: keyof Stats, s: Stats): Trend {
  if (key === 'confirmed_total') {
    const cur = s.confirmed_week ?? 0
    const prev = s.confirmed_prev_week ?? 0
    if (prev === 0 && cur === 0) return { dir: 'flat', pct: '±0', label: 'без изменений' }
    return {
      dir: cur > prev ? 'up' : cur < prev ? 'down' : 'flat',
      pct: pctChange(cur, prev),
      label: 'к прошлой неделе',
    }
  }
  if (key === 'cancelled_week') {
    const cur = s.cancelled_week
    const prev = s.cancelled_prev_week ?? 0
    if (prev === 0 && cur === 0) return { dir: 'flat', pct: '±0', label: 'без изменений' }
    return {
      dir: cur > prev ? 'up' : cur < prev ? 'down' : 'flat',
      pct: pctChange(cur, prev),
      label: 'к прошлой неделе',
    }
  }
  if (key === 'upcoming_events') {
    const cur = s.upcoming_events
    const prev = s.upcoming_prev_week ?? 0
    return {
      dir: cur > prev ? 'up' : cur < prev ? 'down' : 'flat',
      pct: pctChange(cur, prev),
      label: 'к прошлой неделе',
    }
  }
  if (key === 'active_users') {
    const cur = s.active_users
    const prev = s.active_users_prev_week ?? 0
    return {
      dir: cur > prev ? 'up' : cur < prev ? 'down' : 'flat',
      pct: pctChange(cur, prev),
      label: 'новых за неделю',
    }
  }
  return { dir: 'flat', pct: '±0', label: 'без изменений' }
}

const TILES: TileConfig[] = [
  {
    key: 'upcoming_events',
    label: 'Ближайших мероприятий',
    Icon: IconCalendarEvent,
    accent: '#2c54ee',
    bg: 'rgba(238,243,255,0.82)',
    iconBg: 'rgba(44,84,238,0.12)',
    iconColor: '#2c54ee',
  },
  {
    key: 'confirmed_total',
    label: 'Подтверждённых записей',
    Icon: IconCircleCheck,
    accent: '#16a34a',
    bg: 'rgba(220,252,231,0.75)',
    iconBg: 'rgba(22,163,74,0.12)',
    iconColor: '#16a34a',
  },
  {
    key: 'waitlist_total',
    label: 'В листе ожидания',
    Icon: IconHourglassHigh,
    accent: '#f59e0b',
    bg: 'rgba(255,251,235,0.82)',
    iconBg: 'rgba(245,158,11,0.12)',
    iconColor: '#d97706',
  },
  {
    key: 'cancelled_week',
    label: 'Отмен за неделю',
    Icon: IconX,
    accent: '#dc2626',
    bg: 'rgba(254,242,242,0.82)',
    iconBg: 'rgba(220,38,38,0.10)',
    iconColor: '#dc2626',
  },
  {
    key: 'active_users',
    label: 'Активных пользователей',
    Icon: IconUser,
    accent: '#0ea5e9',
    bg: 'rgba(240,249,255,0.82)',
    iconBg: 'rgba(14,165,233,0.12)',
    iconColor: '#0284c7',
  },
]

function SkeletonCard({ delay }: { delay: number }) {
  return (
    <Box
      style={{
        background: 'rgba(255,255,255,0.7)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(226,232,240,0.8)',
        borderRadius: 16,
        padding: '1.5rem',
        animation: `dash-fadeUp 0.4s ${delay}ms ease both`,
      }}
    >
      <Box className="dash-skeleton" style={{ height: 4, borderRadius: 2, marginBottom: 16 }} />
      <Flex justify="space-between" align="flex-start" mb="lg">
        <Box className="dash-skeleton" style={{ width: 48, height: 48, borderRadius: 12 }} />
        <Box className="dash-skeleton" style={{ width: 60, height: 18, borderRadius: 4 }} />
      </Flex>
      <Box className="dash-skeleton" style={{ width: '60%', height: 40, borderRadius: 8, marginBottom: 10 }} />
      <Box className="dash-skeleton" style={{ width: '80%', height: 14, borderRadius: 4 }} />
    </Box>
  )
}

function TrendBadge({ dir, pct, label }: { dir: Trend['dir']; pct: string; label: string }) {
  const arrow = dir === 'up' ? '↑' : dir === 'down' ? '↓' : '→'
  const cls = dir === 'up' ? 'dash-trend-up' : dir === 'down' ? 'dash-trend-down' : 'dash-trend-flat'
  const bg =
    dir === 'up'
      ? 'rgba(22,163,74,0.10)'
      : dir === 'down'
        ? 'rgba(220,38,38,0.10)'
        : 'rgba(148,163,184,0.12)'

  return (
    <Flex direction="column" align="flex-end" gap={2}>
      <Box
        style={{
          background: bg,
          borderRadius: 9999,
          padding: '3px 10px',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <Text fz="xs" fw={700} className={cls} style={{ fontVariantNumeric: 'tabular-nums' }}>
          {arrow} {pct}
        </Text>
      </Box>
      <Text fz={10} c="dimmed" style={{ lineHeight: 1.2, textAlign: 'right', maxWidth: 90 }}>
        {label}
      </Text>
    </Flex>
  )
}

function StatCard({ tile, value, delay, trend }: { tile: TileConfig; value: number; delay: number; trend: Trend }) {
  const { Icon } = tile
  return (
    <Box
      className="dash-stat-card"
      style={{
        background: tile.bg,
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid rgba(226,232,240,0.7)',
        borderRadius: 16,
        padding: '1.5rem',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        animation: `dash-fadeUp 0.45s ${delay}ms cubic-bezier(0.22,1,0.36,1) both`,
      }}
    >
      <Box
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 4,
          borderRadius: '16px 16px 0 0',
          background: tile.accent,
          opacity: 0.9,
        }}
      />

      <Box
        style={{
          position: 'absolute',
          top: -30,
          right: -30,
          width: 120,
          height: 120,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${tile.accent}22, transparent 70%)`,
          pointerEvents: 'none',
        }}
      />

      <Flex justify="space-between" align="flex-start" mb="md">
        <Flex
          align="center"
          justify="center"
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: tile.iconBg,
            color: tile.iconColor,
            flexShrink: 0,
          }}
        >
          <Icon size={24} stroke={1.8} />
        </Flex>
        <TrendBadge dir={trend.dir} pct={trend.pct} label={trend.label} />
      </Flex>

      <Text
        style={{
          fontSize: 'clamp(2rem, 3.5vw, 2.75rem)',
          fontWeight: 700,
          lineHeight: 1.1,
          letterSpacing: '-0.02em',
          color: '#0f172a',
          fontVariantNumeric: 'tabular-nums',
          animation: `dash-countUp 0.5s ${delay + 100}ms cubic-bezier(0.34,1.56,0.64,1) both`,
        }}
      >
        {value.toLocaleString('ru-RU')}
      </Text>

      <Text
        fz="sm"
        mt={6}
        style={{
          color: '#475569',
          lineHeight: 1.4,
          fontWeight: 500,
        }}
      >
        {tile.label}
      </Text>
    </Box>
  )
}

function HeroSummary({ stats }: { stats: Stats }) {
  const isEmpty = Object.values(stats).every((v) => v === 0)

  return (
    <Box
      style={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 20,
        background: 'linear-gradient(135deg, #162f9c 0%, #2c54ee 55%, #cc430a 85%, #ff6b1f 100%)',
        padding: '2rem 2.5rem',
        color: '#fff',
        animation: 'dash-fadeUp 0.5s ease both',
      }}
    >
      <svg
        aria-hidden="true"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.1, pointerEvents: 'none' }}
      >
        <defs>
          <pattern id="dash-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="white" strokeWidth="0.7" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dash-grid)" />
      </svg>

      <Box
        style={{
          position: 'absolute',
          right: -40,
          top: -40,
          width: 200,
          height: 200,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.15), transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      <Flex justify="space-between" align="center" wrap="wrap" gap="md" style={{ position: 'relative', zIndex: 1 }}>
        <Stack gap={4}>
          <Text fz="xs" style={{ opacity: 0.75, letterSpacing: '0.05em', textTransform: 'uppercase', fontWeight: 600 }}>
            Сводка
          </Text>
          <Title
            order={2}
            c="white"
            style={{ fontSize: 'clamp(1.4rem, 2.5vw, 2rem)', lineHeight: 1.15 }}
          >
            {isEmpty
              ? 'Пока пусто — создайте первое мероприятие'
              : `${stats.upcoming_events} мероприятий · ${stats.confirmed_total} записей`}
          </Title>
          <Text style={{ opacity: 0.8, fontSize: '0.92rem', lineHeight: 1.5 }}>
            {isEmpty
              ? 'Перейдите в раздел «Мероприятия», чтобы начать работу'
              : `Лист ожидания: ${stats.waitlist_total} · Активных пользователей: ${stats.active_users}`}
          </Text>
        </Stack>

        {!isEmpty && (
          <Box
            style={{
              background: 'rgba(255,255,255,0.15)',
              backdropFilter: 'blur(8px)',
              border: '1px solid rgba(255,255,255,0.25)',
              borderRadius: 16,
              padding: '1rem 1.5rem',
              textAlign: 'center',
              flexShrink: 0,
            }}
          >
            <Text style={{ fontSize: '2.2rem', fontWeight: 800, lineHeight: 1, letterSpacing: '-0.02em' }}>
              {stats.confirmed_total > 0
                ? `${Math.round((stats.confirmed_total / (stats.confirmed_total + stats.waitlist_total || 1)) * 100)}%`
                : '—'}
            </Text>
            <Text fz="xs" style={{ opacity: 0.75, marginTop: 4, fontWeight: 500 }}>
              конверсия
            </Text>
          </Box>
        )}
      </Flex>
    </Box>
  )
}

function EmptyState() {
  return (
    <Flex
      direction="column"
      align="center"
      justify="center"
      gap="md"
      style={{
        padding: '4rem 2rem',
        animation: 'dash-fadeUp 0.5s ease both',
      }}
    >
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
        <IconInbox size={36} stroke={1.6} />
      </Box>
      <Stack gap={4} align="center">
        <Title order={3} style={{ color: '#0f172a' }}>Пока пусто</Title>
        <Text c="dimmed" ta="center" style={{ maxWidth: 360, lineHeight: 1.6 }}>
          Создайте первое мероприятие — и здесь появится живая статистика записей и пользователей.
        </Text>
      </Stack>
    </Flex>
  )
}

export function DashboardPage() {
  const [range, setRange] = useState<'7d' | '30d'>('7d')

  useEffect(() => {
    injectDashboardStyles()
  }, [])

  const statsQ = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => (await api.get<Stats>('/api/admin/dashboard/stats')).data,
  })
  const timeseriesQ = useQuery({
    queryKey: ['dashboard', 'timeseries', range],
    queryFn: async () =>
      (await api.get<TimeseriesPoint[]>(`/api/admin/dashboard/timeseries?range=${range}`)).data,
  })
  const funnelQ = useQuery({
    queryKey: ['dashboard', 'funnel', range],
    queryFn: async () =>
      (await api.get<FunnelData>(`/api/admin/dashboard/funnel?range=${range}`)).data,
  })

  const stats = statsQ.data ?? null
  const error = statsQ.isError
  const isEmpty = stats ? (stats.confirmed_total === 0 && stats.upcoming_events === 0) : false

  return (
    <Box style={{ position: 'relative', minHeight: '100%' }}>
      <Stack gap="xl" style={{ position: 'relative', zIndex: 1 }}>
        <Stack gap={4} style={{ animation: 'dash-fadeUp 0.35s ease both' }}>
          <Title order={2} style={{ letterSpacing: '-0.01em', color: '#0f172a' }}>
            Сводка
          </Title>
          <Text c="dimmed" fz="sm">
            Состояние системы и регистраций
          </Text>
        </Stack>

        {stats ? (
          <HeroSummary stats={stats} />
        ) : error ? null : (
          <Box
            className="dash-skeleton"
            style={{ height: 130, borderRadius: 20 }}
          />
        )}

        {error && (
          <Flex
            align="center"
            gap="sm"
            style={{
              padding: '1.25rem 1.5rem',
              background: 'rgba(254,242,242,0.9)',
              border: '1px solid rgba(220,38,38,0.2)',
              borderRadius: 12,
              animation: 'dash-fadeUp 0.4s ease both',
            }}
          >
            <Box style={{ color: '#dc2626', display: 'flex' }}>
              <IconAlertTriangle size={22} stroke={1.8} />
            </Box>
            <Stack gap={2}>
              <Text fw={600} fz="sm" style={{ color: '#dc2626' }}>
                Не удалось загрузить статистику
              </Text>
              <Text fz="xs" c="dimmed">
                Проверьте соединение с бэкендом или обновите страницу
              </Text>
            </Stack>
          </Flex>
        )}

        {!stats && !error ? (
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 5 }} spacing="md">
            {TILES.map((_, i) => (
              <SkeletonCard key={i} delay={i * 60} />
            ))}
          </SimpleGrid>
        ) : stats && !isEmpty ? (
          <>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 5 }} spacing="md">
              {TILES.map((tile, i) => (
                <StatCard
                  key={tile.key}
                  tile={tile}
                  value={(stats[tile.key] as number) ?? 0}
                  delay={120 + i * 70}
                  trend={computeTrend(tile.key, stats)}
                />
              ))}
            </SimpleGrid>

            <Flex gap="md" align="center" wrap="wrap">
              <Title order={4} style={{ color: '#0f172a' }}>Динамика и воронка</Title>
              <SegmentedControl
                value={range}
                onChange={(v) => setRange(v as '7d' | '30d')}
                data={[
                  { value: '7d', label: '7 дней' },
                  { value: '30d', label: '30 дней' },
                ]}
                size="sm"
              />
            </Flex>

            <Flex gap="md" align="stretch" wrap="wrap">
              <Paper p="lg" radius="lg" withBorder style={{ flex: '2 1 480px', minWidth: 380 }}>
                <Stack gap="xs" mb="sm">
                  <Text fw={600} style={{ color: '#0f172a' }}>Записи по дням</Text>
                  <Text fz="xs" c="dimmed">
                    Создание записей (confirmed, waitlist) и отмены за выбранный период
                  </Text>
                </Stack>
                <Box style={{ width: '100%', height: 280 }}>
                  <ResponsiveContainer>
                    <LineChart data={timeseriesQ.data ?? []}>
                      <CartesianGrid stroke="rgba(15,23,42,0.06)" />
                      <XAxis
                        dataKey="date"
                        tickFormatter={(d) => d.slice(5)}
                        fontSize={11}
                        stroke="#94a3b8"
                      />
                      <YAxis allowDecimals={false} fontSize={11} stroke="#94a3b8" />
                      <Tooltip
                        labelFormatter={(d) => d}
                        contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0' }}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="confirmed" stroke="#16a34a" name="Подтв." strokeWidth={2} dot={{ r: 3 }} />
                      <Line type="monotone" dataKey="waitlist" stroke="#f59e0b" name="Ожидание" strokeWidth={2} dot={{ r: 3 }} />
                      <Line type="monotone" dataKey="cancelled" stroke="#dc2626" name="Отмены" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </Paper>

              <Paper p="lg" radius="lg" withBorder style={{ flex: '1 1 320px', minWidth: 300 }}>
                <Stack gap="xs" mb="sm">
                  <Text fw={600} style={{ color: '#0f172a' }}>Воронка</Text>
                  <Text fz="xs" c="dimmed">
                    Уникальные пары пользователь × событие за выбранный период
                  </Text>
                </Stack>
                <FunnelView data={funnelQ.data} />
              </Paper>
            </Flex>
          </>
        ) : stats && isEmpty ? (
          <EmptyState />
        ) : null}
      </Stack>
    </Box>
  )
}

function FunnelView({ data }: { data: FunnelData | undefined }) {
  if (!data) {
    return <Box className="dash-skeleton" style={{ height: 200, borderRadius: 12 }} />
  }
  const max = Math.max(data.event_view, 1)
  const items = [
    { key: 'view', label: 'Просмотр карточки', value: data.event_view, color: '#2c54ee' },
    { key: 'start', label: 'Открыли анкету', value: data.form_start, color: '#7c3aed' },
    { key: 'confirm', label: 'Подтвердили', value: data.confirm, color: '#16a34a' },
  ]
  return (
    <Stack gap="sm">
      {items.map((it, idx) => {
        const width = Math.max(8, (it.value / max) * 100)
        const prev = idx === 0 ? null : items[idx - 1].value
        const dropRate = prev !== null && prev > 0 ? Math.round((it.value / prev) * 100) : null
        return (
          <Box key={it.key}>
            <Flex justify="space-between" align="center" mb={4}>
              <Text fz="sm" fw={500}>{it.label}</Text>
              <Flex align="baseline" gap={6}>
                <Text fz="sm" fw={700} style={{ color: it.color, fontVariantNumeric: 'tabular-nums' }}>
                  {it.value}
                </Text>
                {dropRate !== null && (
                  <Text fz="xs" c="dimmed">→ {dropRate}%</Text>
                )}
              </Flex>
            </Flex>
            <Box style={{ width: '100%', height: 10, borderRadius: 5, background: 'rgba(148,163,184,0.15)' }}>
              <Box
                style={{
                  width: `${width}%`,
                  height: '100%',
                  borderRadius: 5,
                  background: it.color,
                  transition: 'width 0.4s ease',
                }}
              />
            </Box>
          </Box>
        )
      })}
    </Stack>
  )
}
