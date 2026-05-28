import {
  ActionIcon, Box, Button, Checkbox, Drawer, Flex, Group, Loader, Menu, Paper, SegmentedControl, Stack,
  Table, Text, TextInput, Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconChevronDown, IconChevronUp, IconDownload, IconFileSpreadsheet, IconFileText,
  IconSearch, IconUsersGroup,
} from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import * as XLSX from 'xlsx'

import { api } from '../api'

import { RegistrationStatusBadge } from './RegistrationStatusBadge'

interface Registration {
  id: string
  user_id: string
  event_id: string
  status: string
  answers: Record<string, unknown>
  waitlist_position: number | null
  checked_in_at: string | null
  is_late_cancellation: boolean
  created_at: string
  short_code?: string | null
  user_first_name?: string | null
  user_last_name?: string | null
  user_username?: string | null
}

function regUserName(r: Registration): string {
  const name = [r.user_first_name, r.user_last_name].filter(Boolean).join(' ').trim()
  return name || r.user_username || r.user_id.slice(0, 8)
}

type RegSortField = 'user' | 'status' | 'created_at' | 'checked_in_at'
type RegSortDir = 'asc' | 'desc'

interface EventField {
  id: string
  key: string
  label: string
  field_type: string
  options?: { value: string; label: string }[] | null
}

const STATUS_FILTERS = [
  { value: 'all',       label: 'Все' },
  { value: 'confirmed', label: 'Подтв.' },
  { value: 'waitlist',  label: 'Очередь' },
  { value: 'cancelled', label: 'Отменено' },
]

function SortHeader({
  label, field, sortField, sortDir, onClick,
}: {
  label: string
  field: RegSortField
  sortField: RegSortField
  sortDir: RegSortDir
  onClick: (f: RegSortField) => void
}) {
  const active = sortField === field
  return (
    <Table.Th
      style={{ cursor: 'pointer', userSelect: 'none' }}
      onClick={() => onClick(field)}
    >
      <Flex align="center" gap={4}>
        <Text fz="sm" fw={600} c={active ? 'brand' : undefined}>{label}</Text>
        {active && (sortDir === 'asc'
          ? <IconChevronUp size={14} stroke={2.2} />
          : <IconChevronDown size={14} stroke={2.2} />)}
      </Flex>
    </Table.Th>
  )
}

const STATUS_RU: Record<string, string> = {
  confirmed: 'Подтверждено',
  waitlist: 'В очереди',
  pending: 'Ожидает',
  cancelled: 'Отменено',
  rejected: 'Отклонено',
}

const DATE_FMT = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
})
const DATE_FMT_FULL = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
})

/** Человекочитаемое значение ответа с учётом типа поля и его вариантов. */
function formatValue(value: unknown, field?: EventField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
  const optMap = new Map((field?.options ?? []).map((o) => [String(o.value), o.label]))
  if (Array.isArray(value)) {
    if (value.length === 0) return '—'
    return value.map((v) => optMap.get(String(v)) ?? String(v)).join(', ')
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return optMap.get(String(value)) ?? String(value)
}

/** Короткий предпросмотр ответов для ячейки таблицы (с подписями полей). */
function answersPreview(answers: Record<string, unknown>, fields: EventField[]): string {
  const byKey = new Map(fields.map((f) => [f.key, f]))
  const entries = Object.entries(answers)
  if (entries.length === 0) return 'Нет ответов'
  return entries
    .map(([k, v]) => {
      const field = byKey.get(k)
      return `${field?.label ?? k}: ${formatValue(v, field)}`
    })
    .join(' · ')
}

/** Матрица для экспорта: первая строка — заголовки, далее — записи. */
function buildExportMatrix(rows: Registration[], fields: EventField[]): (string | number)[][] {
  const baseHeaders = [
    '№', 'ID записи', 'Пользователь', 'Статус', 'Позиция в очереди',
    'Дата записи', 'Отметка о приходе',
  ]
  const fmtDate = (iso: string | null) => (iso ? DATE_FMT_FULL.format(new Date(iso)) : '')
  const matrix: (string | number)[][] = [[...baseHeaders, ...fields.map((f) => f.label)]]
  rows.forEach((r, i) => {
    const base: (string | number)[] = [
      i + 1,
      r.id,
      r.user_id,
      STATUS_RU[r.status] ?? r.status,
      r.waitlist_position ?? '',
      fmtDate(r.created_at),
      r.checked_in_at ? fmtDate(r.checked_in_at) : 'Не пришёл',
    ]
    const fieldVals = fields.map((f) => formatValue(r.answers?.[f.key], f))
    matrix.push([...base, ...fieldVals])
  })
  return matrix
}

function downloadCsv(rows: Registration[], fields: EventField[], filename: string) {
  const matrix = buildExportMatrix(rows, fields)
  const esc = (s: unknown) => '"' + String(s ?? '').replace(/"/g, '""') + '"'
  const csv = matrix.map((row) => row.map(esc).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function downloadXlsx(rows: Registration[], fields: EventField[], filename: string) {
  const matrix = buildExportMatrix(rows, fields)
  const ws = XLSX.utils.aoa_to_sheet(matrix)
  ws['!cols'] = matrix[0].map((_, i) => ({ wch: i === 1 || i === 2 ? 38 : 20 }))
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Записи')
  XLSX.writeFile(wb, filename)
}

export function RegistrationsTable({ eventId }: { eventId: string }) {
  const [regs, setRegs] = useState<Registration[] | null>(null)
  const [fields, setFields] = useState<EventField[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [detail, setDetail] = useState<Registration | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState<RegSortField>('created_at')
  const [sortDir, setSortDir] = useState<RegSortDir>('desc')
  const [visibleCount, setVisibleCount] = useState(100)
  useEffect(() => { setVisibleCount(100) }, [eventId, statusFilter, search])

  // Сбрасываем выбор при смене фильтра / события
  useEffect(() => { setSelected(new Set()) }, [statusFilter, eventId, search])

  function toggleSort(field: RegSortField) {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortField(field)
      setSortDir(field === 'created_at' || field === 'checked_in_at' ? 'desc' : 'asc')
    }
  }

  function toggleOne(id: string) {
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }
  function toggleAll(allIds: string[]) {
    setSelected((s) => {
      if (s.size === allIds.length) return new Set()
      return new Set(allIds)
    })
  }

  useEffect(() => {
    api.get<EventField[]>(`/api/admin/events/${eventId}/fields`)
      .then((r) => setFields(r.data))
      .catch(() => setFields([]))
  }, [eventId])

  useEffect(() => {
    setLoading(true)
    const t = setTimeout(() => {
      const params = new URLSearchParams({ limit: '500' })
      if (statusFilter !== 'all') params.set('status', statusFilter)
      if (search.trim()) params.set('q', search.trim())
      api.get<Registration[]>(`/api/admin/events/${eventId}/registrations?${params.toString()}`)
        .then((r) => setRegs(r.data))
        .catch(() =>
          notifications.show({ color: 'red', title: 'Не удалось загрузить записи', message: '' }),
        )
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [eventId, statusFilter, search])

  const sortedRegs = useMemo(() => {
    if (!regs) return regs
    const sign = sortDir === 'asc' ? 1 : -1
    return [...regs].sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case 'user':
          cmp = regUserName(a).localeCompare(regUserName(b), 'ru')
          break
        case 'status':
          cmp = a.status.localeCompare(b.status)
          break
        case 'checked_in_at':
          cmp = (a.checked_in_at ? new Date(a.checked_in_at).getTime() : 0) -
                (b.checked_in_at ? new Date(b.checked_in_at).getTime() : 0)
          break
        case 'created_at':
        default:
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      }
      return cmp * sign
    })
  }, [regs, sortField, sortDir])

  const counts = useMemo(() => {
    if (!regs) return { total: 0, confirmed: 0, waitlist: 0 }
    return {
      total: regs.length,
      confirmed: regs.filter((r) => r.status === 'confirmed').length,
      waitlist: regs.filter((r) => r.status === 'waitlist').length,
    }
  }, [regs])

  if (loading || !regs) {
    return <Flex justify="center" align="center" py="xl"><Loader /></Flex>
  }

  return (
    <Stack gap="lg">
      <Flex justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <Stack gap={4}>
          <Title order={5} style={{ color: '#0f172a' }}>Записи на мероприятие</Title>
          <Text fz="xs" c="dimmed">
            Всего: {counts.total} · Подтверждено: {counts.confirmed} · Очередь: {counts.waitlist}
          </Text>
        </Stack>
        <Flex gap="sm" wrap="wrap">
          <TextInput
            placeholder="Поиск: ФИО / username / код"
            leftSection={<IconSearch size={14} stroke={1.8} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            size="sm"
            w={260}
          />
          <SegmentedControl
            value={statusFilter}
            onChange={setStatusFilter}
            data={STATUS_FILTERS}
            size="sm"
          />
          <Menu shadow="md" position="bottom-end" width={220}>
            <Menu.Target>
              <ActionIcon
                variant="light"
                size="lg"
                aria-label="Экспорт записей"
                disabled={regs.length === 0}
              >
                <IconDownload size={18} stroke={1.8} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>Экспорт записей</Menu.Label>
              <Menu.Item
                leftSection={<IconFileSpreadsheet size={16} stroke={1.8} />}
                onClick={() => {
                  // server-side XLSX (с заголовком, форматированием, всеми колонками)
                  window.location.href = `/api/admin/events/${eventId}/registrations.xlsx`
                }}
              >
                Excel (.xlsx)
              </Menu.Item>
              <Menu.Item
                leftSection={<IconFileSpreadsheet size={16} stroke={1.8} />}
                onClick={() => downloadXlsx(regs, fields, `Записи-${eventId.slice(0, 8)}.xlsx`)}
              >
                Excel (текущая выборка)
              </Menu.Item>
              <Menu.Item
                leftSection={<IconFileText size={16} stroke={1.8} />}
                onClick={() => downloadCsv(regs, fields, `Записи-${eventId.slice(0, 8)}.csv`)}
              >
                CSV (для отладки)
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Flex>
      </Flex>

      {regs.length === 0 ? (
        <Paper withBorder p="xl" radius="lg">
          <Stack align="center" gap="sm">
            <Box
              style={{
                width: 56, height: 56, borderRadius: 14, background: 'rgba(44,84,238,0.08)',
                color: '#2c54ee', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <IconUsersGroup size={28} stroke={1.6} />
            </Box>
            <Stack gap={2} align="center">
              <Text fw={600} style={{ color: '#0f172a' }}>
                {statusFilter === 'all' ? 'Записей пока нет' : 'Нет записей с таким статусом'}
              </Text>
              <Text fz="sm" c="dimmed" ta="center" style={{ maxWidth: 360 }}>
                {statusFilter === 'all'
                  ? 'Поделитесь ссылкой на бота — после первой записи здесь появится таблица с участниками и их ответами.'
                  : 'Попробуйте сменить фильтр статуса.'}
              </Text>
            </Stack>
          </Stack>
        </Paper>
      ) : (
        <Stack gap="sm">
          {selected.size > 0 && (
            <Paper
              p="sm"
              radius="md"
              withBorder
              style={{ background: 'rgba(44,84,238,0.06)', borderColor: 'rgba(44,84,238,0.25)' }}
            >
              <Flex justify="space-between" align="center" gap="md" wrap="wrap">
                <Text fz="sm" fw={600} style={{ color: '#1e3fcc' }}>
                  Выбрано: {selected.size}
                </Text>
                <Group gap="xs">
                  <Button
                    variant="light"
                    size="xs"
                    leftSection={<IconFileSpreadsheet size={14} stroke={1.8} />}
                    onClick={() => {
                      const subset = (sortedRegs ?? regs).filter((r) => selected.has(r.id))
                      downloadXlsx(subset, fields, `Записи-выбрано-${subset.length}.xlsx`)
                    }}
                  >
                    Excel выбранных
                  </Button>
                  <Button
                    variant="light"
                    size="xs"
                    leftSection={<IconFileText size={14} stroke={1.8} />}
                    onClick={() => {
                      const subset = (sortedRegs ?? regs).filter((r) => selected.has(r.id))
                      downloadCsv(subset, fields, `Записи-выбрано-${subset.length}.csv`)
                    }}
                  >
                    CSV выбранных
                  </Button>
                  <Button variant="subtle" size="xs" onClick={() => setSelected(new Set())}>
                    Сбросить
                  </Button>
                </Group>
              </Flex>
            </Paper>
          )}
          <Paper withBorder radius="lg" style={{ overflow: 'hidden' }}>
          <Table verticalSpacing="md" horizontalSpacing="lg" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th style={{ width: 40 }}>
                  <Checkbox
                    aria-label="Выбрать всё"
                    checked={selected.size === regs.length && regs.length > 0}
                    indeterminate={selected.size > 0 && selected.size < regs.length}
                    onChange={() => toggleAll(regs.map((r) => r.id))}
                  />
                </Table.Th>
                <SortHeader label="Участник" field="user"  sortField={sortField} sortDir={sortDir} onClick={toggleSort} />
                <SortHeader label="Статус"   field="status" sortField={sortField} sortDir={sortDir} onClick={toggleSort} />
                <Table.Th>Ответы</Table.Th>
                <SortHeader label="Создано"  field="created_at" sortField={sortField} sortDir={sortDir} onClick={toggleSort} />
                <SortHeader label="Чек-ин"   field="checked_in_at" sortField={sortField} sortDir={sortDir} onClick={toggleSort} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(sortedRegs ?? regs).slice(0, visibleCount).map((r) => {
                const count = Object.keys(r.answers ?? {}).length
                return (
                  <Table.Tr key={r.id}>
                    <Table.Td>
                      <Checkbox
                        aria-label={`Выбрать запись ${regUserName(r)}`}
                        checked={selected.has(r.id)}
                        onChange={() => toggleOne(r.id)}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={0}>
                        <Text fw={500} style={{ color: '#0f172a' }}>{regUserName(r)}</Text>
                        {r.user_username && (
                          <Text fz="xs" c="dimmed">@{r.user_username}</Text>
                        )}
                        {r.short_code && (
                          <Text fz="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                            {r.short_code}
                          </Text>
                        )}
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Flex direction="column" gap={2}>
                        <RegistrationStatusBadge status={r.status} />
                        {r.status === 'waitlist' && r.waitlist_position !== null && (
                          <Text fz="xs" c="dimmed">в очереди #{r.waitlist_position}</Text>
                        )}
                        {r.is_late_cancellation && (
                          <Text fz="xs" c="orange" fw={500}>
                            🕒 Поздняя отмена
                          </Text>
                        )}
                      </Flex>
                    </Table.Td>
                    <Table.Td style={{ maxWidth: 360 }}>
                      {count === 0 ? (
                        <Text fz="sm" c="dimmed">—</Text>
                      ) : (
                        <Button
                          variant="subtle"
                          size="compact-sm"
                          onClick={() => setDetail(r)}
                          styles={{
                            root: { maxWidth: '100%', height: 'auto', padding: '4px 8px' },
                            label: {
                              whiteSpace: 'normal', textAlign: 'left', fontWeight: 400,
                              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                            },
                          }}
                        >
                          {answersPreview(r.answers, fields)}
                        </Button>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text fz="sm" c="dimmed">{DATE_FMT.format(new Date(r.created_at))}</Text>
                    </Table.Td>
                    <Table.Td>
                      {r.checked_in_at ? (
                        <Text fz="sm" c="teal">{DATE_FMT.format(new Date(r.checked_in_at))}</Text>
                      ) : (
                        <Text fz="sm" c="dimmed">—</Text>
                      )}
                    </Table.Td>
                  </Table.Tr>
                )
              })}
            </Table.Tbody>
          </Table>
          </Paper>
          {(sortedRegs ?? regs).length > visibleCount && (
            <Flex justify="center">
              <Button
                variant="default"
                size="sm"
                onClick={() => setVisibleCount((n) => n + 100)}
              >
                Показать ещё ({(sortedRegs ?? regs).length - visibleCount})
              </Button>
            </Flex>
          )}
        </Stack>
      )}

      <Drawer
        opened={detail !== null}
        onClose={() => setDetail(null)}
        position="right"
        size="md"
        padding="lg"
        title={<Title order={4} style={{ color: '#0f172a' }}>Запись участника</Title>}
        overlayProps={{ opacity: 0.35, blur: 2 }}
      >
        {detail && (
          <Stack gap="md">
            <Stack gap={4}>
              <Flex gap="sm" align="center" wrap="wrap">
                <RegistrationStatusBadge status={detail.status} />
                <Text fz="xs" c="dimmed">
                  Записан: {DATE_FMT_FULL.format(new Date(detail.created_at))}
                </Text>
              </Flex>
              {detail.checked_in_at && (
                <Text fz="xs" c="teal">
                  ✅ Чек-ин: {DATE_FMT_FULL.format(new Date(detail.checked_in_at))}
                </Text>
              )}
            </Stack>
            <Box style={{ borderTop: '1px solid var(--color-neutral-200)' }} />
            <Stack gap={2}>
              <Text fz="xs" c="dimmed" tt="uppercase" fw={600} mb={4}>Ответы анкеты</Text>
              {fields.length === 0 && Object.keys(detail.answers ?? {}).length === 0 && (
                <Text fz="sm" c="dimmed">Нет ответов.</Text>
              )}
              {fields.map((f) => (
                <AnswerRow key={f.id} label={f.label} value={formatValue(detail.answers?.[f.key], f)} />
              ))}
              {Object.keys(detail.answers ?? {})
                .filter((k) => !fields.some((f) => f.key === k))
                .map((k) => (
                  <AnswerRow key={k} label={k} value={formatValue(detail.answers[k])} />
                ))}
            </Stack>
          </Stack>
        )}
      </Drawer>
    </Stack>
  )
}

function AnswerRow({ label, value }: { label: string; value: string }) {
  return (
    <Flex
      justify="space-between"
      gap="md"
      py={8}
      style={{ borderBottom: '1px solid #f1f5f9' }}
    >
      <Text fz="sm" c="dimmed" style={{ flexShrink: 0, maxWidth: '45%' }}>{label}</Text>
      <Text fz="sm" style={{ textAlign: 'right', color: '#0f172a', whiteSpace: 'pre-wrap' }}>
        {value}
      </Text>
    </Flex>
  )
}
