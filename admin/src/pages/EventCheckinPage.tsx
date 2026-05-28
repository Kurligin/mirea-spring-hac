import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Flex,
  Group,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import {
  IconArrowLeft,
  IconCheck,
  IconQrcode,
  IconRefresh,
  IconSearch,
  IconX,
} from '@tabler/icons-react'
import { Html5Qrcode } from 'html5-qrcode'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api'
import { useAuthStore } from '../stores/auth'

interface EventCheckinStats {
  event_id: string
  event_title: string
  starts_at: string
  capacity: number | null
  confirmed: number
  checked_in: number
  remaining_confirmed: number
  waitlist: number
  cancelled: number
}

interface CheckinRegRow {
  id: string
  user_name: string
  short_code: string | null
  status: 'pending' | 'confirmed' | 'cancelled' | 'waitlist'
  checked_in_at: string | null
  is_late_cancellation: boolean
  created_at: string
}

interface CheckinResult {
  registration_id: string
  user_name: string
  event_title: string
  short_code: string | null
  status: string
  checked_in_at: string
  already_checked_in: boolean
}

type Outcome =
  | { kind: 'ok'; result: CheckinResult }
  | { kind: 'error'; message: string }

const READER_ID = 'qr-reader-event'

function cameraErrorHint(err: unknown): string {
  const name = (err as { name?: string })?.name ?? ''
  const ua = navigator.userAgent
  const isMac = /Macintosh/.test(ua)
  const isIOS = /iPhone|iPad|iPod/.test(ua)
  const isSafari = /^((?!chrome|android).)*safari/i.test(ua)
  const isFirefox = /Firefox/i.test(ua)
  const isChrome = /Chrome/i.test(ua) && !/Edg/i.test(ua)

  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    if (isIOS && isSafari) {
      return 'Доступ к камере запрещён. На iOS: «Настройки → Safari → Камера → Разрешить», затем обновите страницу.'
    }
    if (isMac && isSafari) {
      return 'Доступ к камере запрещён. Safari → Настройки → Веб-сайты → Камера → выбрать «localhost» и поставить «Разрешить». Затем обновите страницу.'
    }
    if (isChrome) {
      return 'Доступ к камере запрещён. Кликните иконку 🔒/⚙️ слева от адреса → Камера → «Разрешить». Затем обновите страницу.'
    }
    if (isFirefox) {
      return 'Доступ к камере запрещён. Откройте иконку слева от адреса → разрешите камеру для этого сайта. Затем обновите страницу.'
    }
    return 'Доступ к камере запрещён. Откройте настройки сайта и разрешите камеру.'
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return 'Камера не найдена. Проверьте, что устройство имеет камеру и не используется другим приложением.'
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'Камера занята другим приложением. Закройте Zoom/FaceTime и попробуйте снова.'
  }
  if (name === 'OverconstrainedError') {
    return 'Камера не подходит. Попробуйте выбрать другую в селекторе.'
  }
  return 'Не удалось включить камеру. Проверьте разрешения и попробуйте снова.'
}

const ERROR_MESSAGES: Record<string, string> = {
  QR_INVALID: 'QR-код не наш или повреждён.',
  QR_EXPIRED: 'QR-код устарел — попросите обновить экран в боте.',
  NOT_CONFIRMED: 'Запись не подтверждена — отметить нельзя.',
  FOREIGN_EVENT: 'QR от другого мероприятия — направьте к коллеге.',
  CODE_NOT_FOUND: 'Код не найден среди записей этого события.',
  EMPTY_CODE: 'Введите короткий код.',
}

const DATE_FMT = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
})

export function EventCheckinPage() {
  const { id: eventId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.profile?.role)
  const backTo = role === 'controller' ? '/controller' : `/events/${eventId}`
  const [stats, setStats] = useState<EventCheckinStats | null>(null)
  const [regs, setRegs] = useState<CheckinRegRow[] | null>(null)
  const [query, setQuery] = useState('')
  const [manualCode, setManualCode] = useState('')
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [busy, setBusy] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [cameras, setCameras] = useState<{ id: string; label: string }[]>([])
  const [cameraId, setCameraId] = useState<string | null>(
    () => localStorage.getItem('admin.scanner.cameraId'),
  )
  const scannerRef = useRef<Html5Qrcode | null>(null)

  useEffect(() => {
    if (cameraId) localStorage.setItem('admin.scanner.cameraId', cameraId)
  }, [cameraId])

  const loadCameras = useCallback(async () => {
    try {
      const list = await Html5Qrcode.getCameras()
      const mapped = list.map((c) => ({ id: c.id, label: c.label || `Камера ${c.id.slice(0, 6)}` }))
      setCameras(mapped)
      if (!cameraId && list.length > 0) {
        const back = list.find((c) => /back|rear|задн/i.test(c.label))
        setCameraId(back?.id ?? list[list.length - 1]?.id ?? list[0].id)
      }
    } catch {
      /* permission denied / no cameras */
    }
  }, [cameraId])

  const refreshStats = useCallback(async () => {
    if (!eventId) return
    const { data } = await api.get<EventCheckinStats>(
      `/api/admin/events/${eventId}/checkin/stats`,
    )
    setStats(data)
  }, [eventId])

  const refreshRegs = useCallback(
    async (q?: string) => {
      if (!eventId) return
      const params = q ? `?q=${encodeURIComponent(q)}` : ''
      const { data } = await api.get<CheckinRegRow[]>(
        `/api/admin/events/${eventId}/checkin/registrations${params}`,
      )
      setRegs(data)
    },
    [eventId],
  )

  useEffect(() => {
    void refreshStats()
    void refreshRegs()
    // Auto-prepare: пытаемся узнать список камер при заходе на страницу,
    // чтобы первая кнопка «Сканировать» сработала сразу. На iOS без user-gesture
    // вызов provалится — это OK, fallback на ленивую инициализацию.
    void loadCameras()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshStats, refreshRegs])

  useEffect(() => {
    const t = setTimeout(() => void refreshRegs(query.trim() || undefined), 250)
    return () => clearTimeout(t)
  }, [query, refreshRegs])

  const stopScanner = useCallback(async () => {
    const s = scannerRef.current
    scannerRef.current = null
    if (s) {
      try {
        await s.stop()
      } catch {
        /* already stopped */
      }
      try {
        s.clear()
      } catch {
        /* ignore */
      }
    }
    setScanning(false)
  }, [])

  useEffect(() => () => void stopScanner(), [stopScanner])

  const [bigVisible, setBigVisible] = useState(false)
  const bigTimerRef = useRef<number | null>(null)

  const applyOutcome = useCallback(
    (kind: Outcome['kind'], data: unknown) => {
      if (kind === 'ok') {
        setOutcome({ kind: 'ok', result: data as CheckinResult })
        void refreshStats()
        void refreshRegs(query.trim() || undefined)
      } else {
        setOutcome({ kind: 'error', message: data as string })
      }
      setBigVisible(true)
      if (bigTimerRef.current) window.clearTimeout(bigTimerRef.current)
      // Успех/уже отмечен — короткое сообщение с auto-close.
      // Ошибки — не закрываем, юзер должен прочитать инструкцию.
      if (kind === 'ok') {
        bigTimerRef.current = window.setTimeout(() => setBigVisible(false), 1500)
      }
    },
    [refreshStats, refreshRegs, query],
  )

  useEffect(() => () => {
    if (bigTimerRef.current) window.clearTimeout(bigTimerRef.current)
  }, [])

  const errorMessage = (e: unknown): string => {
    const resp = (e as { response?: { data?: { detail?: string }; status?: number } })
      .response
    const code = resp?.data?.detail
    return (
      (code && ERROR_MESSAGES[code]) ||
      (resp?.status === 404 ? 'Запись не найдена.' : 'Ошибка. Попробуйте ещё раз.')
    )
  }

  const handleScanned = useCallback(
    async (text: string) => {
      if (!eventId) return
      setBusy(true)
      await stopScanner()
      try {
        const { data } = await api.post<CheckinResult>('/api/admin/checkin', {
          payload: text,
          event_id: eventId,
        })
        applyOutcome('ok', data)
      } catch (e) {
        applyOutcome('error', errorMessage(e))
      } finally {
        setBusy(false)
      }
    },
    [eventId, stopScanner, applyOutcome],
  )

  const startScannerWith = useCallback(
    async (deviceId: string | null) => {
      setOutcome(null)
      setScanning(true)
      const scanner = new Html5Qrcode(READER_ID)
      scannerRef.current = scanner
      const config = { fps: 10, qrbox: { width: 260, height: 260 } }

      const tryStart = async (source: string | { facingMode: 'environment' | 'user' }) => {
        await scanner.start(
          source,
          config,
          (decoded) => {
            if (scannerRef.current) void handleScanned(decoded)
          },
          () => {
            /* per-frame errors — ignore */
          },
        )
      }

      // Шаг 1: попытка по сохранённому deviceId (если есть)
      if (deviceId) {
        try {
          await tryStart(deviceId)
          void loadCameras()
          return
        } catch {
          localStorage.removeItem('admin.scanner.cameraId')
          setCameraId(null)
        }
      }

      // Шаг 2: запросить камеру через facingMode — html5-qrcode сам триггернёт getUserMedia
      try {
        await tryStart({ facingMode: 'environment' })
        void loadCameras()
        return
      } catch {
        // Шаг 3: явный getUserMedia — иногда триггерит prompt, который не вызвался у библиотеки
        try {
          if (!navigator.mediaDevices?.getUserMedia) {
            throw new Error('mediaDevices unavailable')
          }
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' },
          })
          stream.getTracks().forEach((t) => t.stop())
          await loadCameras()
          await tryStart({ facingMode: 'environment' })
          return
        } catch (err) {
          scannerRef.current = null
          setScanning(false)
          applyOutcome('error', cameraErrorHint(err))
        }
      }
    },
    [handleScanned, applyOutcome, loadCameras],
  )

  const startScanner = useCallback(() => startScannerWith(cameraId), [startScannerWith, cameraId])

  const submitManualCode = useCallback(async () => {
    if (!eventId) return
    const code = manualCode.trim()
    if (!code) return
    setBusy(true)
    try {
      const { data } = await api.post<CheckinResult>(
        `/api/admin/events/${eventId}/checkin/by-code`,
        { short_code: code },
      )
      applyOutcome('ok', data)
      setManualCode('')
    } catch (e) {
      applyOutcome('error', errorMessage(e))
    } finally {
      setBusy(false)
    }
  }, [eventId, manualCode, applyOutcome])

  const manualRowCheckin = async (regId: string) => {
    if (!eventId) return
    setBusy(true)
    try {
      const { data } = await api.post<CheckinResult>(
        `/api/admin/events/${eventId}/checkin/manual/${regId}`,
      )
      applyOutcome('ok', data)
    } catch (e) {
      applyOutcome('error', errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const undoCheckin = async (regId: string) => {
    if (!eventId) return
    setBusy(true)
    try {
      await api.post(`/api/admin/events/${eventId}/checkin/uncheck/${regId}`)
      await refreshStats()
      await refreshRegs(query.trim() || undefined)
      setOutcome(null)
    } catch (e) {
      applyOutcome('error', errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap="lg">
      <Group gap="sm">
        <ActionIcon variant="subtle" onClick={() => navigate(backTo)}>
          <IconArrowLeft size={20} />
        </ActionIcon>
        <Stack gap={2}>
          <Title order={3} style={{ color: '#0f172a' }}>
            Контроль входа{stats ? ` · ${stats.event_title}` : ''}
          </Title>
          <Text c="dimmed" fz="sm">
            {stats ? DATE_FMT.format(new Date(stats.starts_at)) : '—'}
          </Text>
        </Stack>
      </Group>

      {/* Stats row — 2 колонки на мобиле, 4 на десктопе */}
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        <StatTile label="Зарегистрировано" value={stats?.confirmed ?? '—'} color="#2c54ee" />
        <StatTile label="Пришло" value={stats?.checked_in ?? '—'} color="#10b981" />
        <StatTile
          label="Осталось"
          value={stats?.remaining_confirmed ?? '—'}
          color="#f59e0b"
        />
        <StatTile label="Лист ожидания" value={stats?.waitlist ?? '—'} color="#64748b" />
      </SimpleGrid>

      <Flex
        direction={{ base: 'column', md: 'row' }}
        align="stretch"
        gap="lg"
        wrap="wrap"
      >
        {/* Scanner + manual code (вверху на мобиле, слева на десктопе) */}
        <Stack gap="md" style={{ flex: '1 1 320px', minWidth: 0, maxWidth: '100%' }}>
          <Paper withBorder radius="lg" p="md">
            <Stack gap="sm">
              <Text fw={600} style={{ color: '#0f172a' }}>
                Сканер QR
              </Text>

              {cameras.length > 1 && (
                <Select
                  label="Камера"
                  data={cameras.map((c) => ({ value: c.id, label: c.label }))}
                  value={cameraId}
                  onChange={async (newId) => {
                    if (!newId || newId === cameraId) return
                    setCameraId(newId)
                    if (scanning) {
                      await stopScanner()
                      setTimeout(() => void startScannerWith(newId), 50)
                    }
                  }}
                  size="sm"
                />
              )}

              {!scanning && (
                <Button
                  size="lg"
                  fullWidth
                  leftSection={<IconQrcode size={20} stroke={1.8} />}
                  onClick={() => void startScanner()}
                  loading={busy}
                  style={{ background: 'linear-gradient(135deg,#2c54ee,#1e3fcc)' }}
                >
                  {outcome ? 'Сканировать ещё' : 'Включить камеру'}
                </Button>
              )}

              <Box id={READER_ID} style={{ display: scanning ? 'block' : 'none', width: '100%' }} />
              {scanning && (
                <Button variant="default" onClick={() => void stopScanner()}>
                  Остановить камеру
                </Button>
              )}
            </Stack>
          </Paper>

          <Paper withBorder radius="lg" p="md">
            <Stack gap="sm">
              <Text fw={600} style={{ color: '#0f172a' }}>
                Ручной ввод кода
              </Text>
              <Text c="dimmed" fz="xs">
                Если QR не сканируется — введите короткий код из подтверждения (например{' '}
                <code>ZRA-0610</code>).
              </Text>
              <Flex gap="xs" wrap="wrap">
                <TextInput
                  placeholder="ABC-1234"
                  value={manualCode}
                  onChange={(e) => setManualCode(e.currentTarget.value.toUpperCase())}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void submitManualCode()
                  }}
                  style={{ flex: '1 1 160px', minWidth: 0 }}
                  inputMode="text"
                  autoCapitalize="characters"
                />
                <Button onClick={() => void submitManualCode()} loading={busy}>
                  Отметить
                </Button>
              </Flex>
            </Stack>
          </Paper>

        </Stack>

        {/* Registrations list (внизу на мобиле, справа на десктопе) */}
        <Paper withBorder radius="lg" style={{ flex: '1 1 380px', minWidth: 0, overflow: 'hidden' }}>
          <Box p="md" style={{ borderBottom: '1px solid var(--color-neutral-100)' }}>
            <Group justify="space-between" align="center" mb="sm">
              <Text fw={600} style={{ color: '#0f172a' }}>
                Зарегистрированные
              </Text>
              <ActionIcon variant="subtle" onClick={() => void refreshRegs(query.trim() || undefined)}>
                <IconRefresh size={18} />
              </ActionIcon>
            </Group>
            <TextInput
              placeholder="Поиск по ФИО или коду"
              leftSection={<IconSearch size={16} />}
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
            />
          </Box>

          <Box style={{ maxHeight: 540, overflowY: 'auto' }}>
            {regs === null ? (
              <Text c="dimmed" ta="center" py="lg">
                Загрузка…
              </Text>
            ) : regs.length === 0 ? (
              <Text c="dimmed" ta="center" py="lg">
                Ничего не найдено
              </Text>
            ) : (
              <Table verticalSpacing="sm" horizontalSpacing="md">
                <Table.Tbody>
                  {regs.map((r) => {
                    const checked = r.checked_in_at !== null
                    return (
                      <Table.Tr key={r.id}>
                        <Table.Td>
                          <Stack gap={0}>
                            <Text fw={500} style={{ color: '#0f172a' }}>
                              {r.user_name}
                            </Text>
                            <Group gap="xs">
                              {r.short_code && (
                                <Text fz="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                                  {r.short_code}
                                </Text>
                              )}
                              {r.status === 'waitlist' && (
                                <Badge color="gray" size="xs">
                                  лист ожидания
                                </Badge>
                              )}
                              {r.status === 'cancelled' && (
                                <Badge color={r.is_late_cancellation ? 'orange' : 'gray'} size="xs">
                                  {r.is_late_cancellation ? '🕒 поздняя отмена' : 'отменена'}
                                </Badge>
                              )}
                            </Group>
                          </Stack>
                        </Table.Td>
                        <Table.Td style={{ width: 1, whiteSpace: 'nowrap' }}>
                          {r.status === 'cancelled' ? (
                            <Text fz="xs" c="dimmed">
                              —
                            </Text>
                          ) : checked ? (
                            <Button
                              size="xs"
                              variant="light"
                              color="teal"
                              leftSection={<IconCheck size={14} />}
                              onClick={() => void undoCheckin(r.id)}
                              disabled={busy}
                            >
                              Пришёл
                            </Button>
                          ) : r.status === 'confirmed' ? (
                            <Button
                              size="xs"
                              variant="default"
                              onClick={() => void manualRowCheckin(r.id)}
                              disabled={busy}
                            >
                              Отметить
                            </Button>
                          ) : (
                            <Badge color="gray" size="sm">
                              не подтв.
                            </Badge>
                          )}
                        </Table.Td>
                      </Table.Tr>
                    )
                  })}
                </Table.Tbody>
              </Table>
            )}
          </Box>
        </Paper>
      </Flex>

      {bigVisible && outcome && (
        <BigResultOverlay
          outcome={outcome}
          onClose={() => setBigVisible(false)}
        />
      )}
    </Stack>
  )
}

function BigResultOverlay({ outcome, onClose }: { outcome: Outcome; onClose: () => void }) {
  const isOk = outcome.kind === 'ok'
  const bg = isOk
    ? outcome.result.already_checked_in
      ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
      : 'linear-gradient(135deg, #16a34a 0%, #0f7c3a 100%)'
    : 'linear-gradient(135deg, #dc2626 0%, #991b1b 100%)'
  const title = isOk
    ? outcome.result.already_checked_in
      ? 'Уже отмечен'
      : 'Отметка прошла'
    : 'Ошибка'
  const subtitle = isOk ? outcome.result.user_name : outcome.message

  return (
    <Box
      onClick={isOk ? onClose : undefined}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        animation: 'big-fade-in 0.18s ease-out',
        cursor: isOk ? 'pointer' : 'default',
        padding: '1rem',
      }}
    >
      <style>{`
        @keyframes big-fade-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes big-pop {
          0%   { transform: scale(0.85); opacity: 0; }
          70%  { transform: scale(1.04); opacity: 1; }
          100% { transform: scale(1.0); opacity: 1; }
        }
      `}</style>
      <Box
        style={{
          width: 'min(560px, 92vw)',
          padding: 'clamp(1.5rem, 6vw, 3rem) clamp(1.25rem, 5vw, 2.5rem)',
          borderRadius: 24,
          background: bg,
          color: '#fff',
          textAlign: 'center',
          boxShadow: '0 24px 48px rgba(0,0,0,0.4)',
          animation: 'big-pop 0.28s cubic-bezier(0.22,1,0.36,1)',
        }}
      >
        <Box
          style={{
            width: 96,
            height: 96,
            margin: '0 auto 1.5rem',
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.18)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {isOk
            ? <IconCheck size={56} stroke={3} />
            : <IconX size={56} stroke={3} />}
        </Box>
        <Text style={{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1.15 }}>
          {title}
        </Text>
        {subtitle && (
          <Text mt="md" style={{ fontSize: '1.15rem', opacity: 0.95, lineHeight: 1.45 }}>
            {subtitle}
          </Text>
        )}
        {isOk && outcome.result.short_code && (
          <Text
            mt="md"
            style={{
              fontFamily: 'monospace',
              fontSize: '1.4rem',
              letterSpacing: '0.1em',
              opacity: 0.9,
            }}
          >
            {outcome.result.short_code}
          </Text>
        )}
        {!isOk && (
          <Button
            mt="xl"
            size="md"
            onClick={(ev) => { ev.stopPropagation(); onClose() }}
            style={{
              background: 'rgba(255,255,255,0.18)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.32)',
            }}
          >
            Закрыть
          </Button>
        )}
      </Box>
    </Box>
  )
}

function StatTile({
  label,
  value,
  color,
}: {
  label: string
  value: number | string
  color: string
}) {
  return (
    <Paper withBorder radius="lg" p="md">
      <Stack gap={4}>
        <Text fz="xs" c="dimmed" tt="uppercase" fw={600} lts={0.4}>
          {label}
        </Text>
        <Text fw={700} fz={28} style={{ color, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </Text>
      </Stack>
    </Paper>
  )
}

