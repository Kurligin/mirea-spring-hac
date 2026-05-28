import { Alert, Box, Button, Group, Paper, Select, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { IconAlertTriangle, IconCheck, IconQrcode } from '@tabler/icons-react'
import { Html5Qrcode } from 'html5-qrcode'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api'

interface CheckinResult {
  registration_id: string
  event_title: string
  user_name: string
  status: string
  short_code: string | null
  checked_in_at: string
  already_checked_in: boolean
}

type Outcome = { kind: 'ok'; result: CheckinResult } | { kind: 'error'; message: string }

const READER_ID = 'qr-reader'

const ERROR_MESSAGES: Record<string, string> = {
  QR_INVALID: 'QR-код не наш или повреждён.',
  QR_EXPIRED: 'QR-код устарел — попросите обновить экран.',
  NOT_CONFIRMED: 'Запись не подтверждена — отметить нельзя.',
}

export function ScannerPage() {
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const [scanning, setScanning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [cameras, setCameras] = useState<{ id: string; label: string }[]>([])
  const [cameraId, setCameraId] = useState<string | null>(
    () => localStorage.getItem('admin.scanner.cameraId'),
  )

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
    } catch {}
  }, [cameraId])

  const stopScanner = useCallback(async () => {
    const s = scannerRef.current
    scannerRef.current = null
    if (s) {
      try {
        await s.stop()
      } catch {
        /* уже остановлен */
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

  const handleScanned = useCallback(
    async (text: string) => {
      setBusy(true)
      await stopScanner()
      try {
        const { data } = await api.post<CheckinResult>('/api/admin/checkin', { payload: text })
        setOutcome({ kind: 'ok', result: data })
      } catch (e) {
        const resp = (e as { response?: { data?: { detail?: string }; status?: number } }).response
        const code = resp?.data?.detail
        const message =
          (code && ERROR_MESSAGES[code]) ||
          (resp?.status === 404
            ? 'Запись не найдена.'
            : 'Не удалось отметить. Попробуйте ещё раз.')
        setOutcome({ kind: 'error', message })
      } finally {
        setBusy(false)
      }
    },
    [stopScanner],
  )

  const startScannerWith = useCallback(
    async (deviceId: string | null) => {
      setOutcome(null)
      setScanning(true)
      const scanner = new Html5Qrcode(READER_ID)
      scannerRef.current = scanner
      try {
        await scanner.start(
          deviceId ?? { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 240, height: 240 } },
          (decoded) => {
            if (scannerRef.current) void handleScanned(decoded)
          },
          () => {
            /* промежуточные ошибки кадра игнорируем */
          },
        )
        void loadCameras()
      } catch {
        scannerRef.current = null
        setScanning(false)
        setOutcome({
          kind: 'error',
          message: 'Не удалось включить камеру. Разрешите доступ в браузере.',
        })
      }
    },
    [handleScanned, loadCameras],
  )

  const startScanner = useCallback(() => startScannerWith(cameraId), [startScannerWith, cameraId])

  return (
    <Stack gap="lg">
      <Stack gap={4}>
        <Title order={3} style={{ color: '#0f172a' }}>
          Сканер QR-кодов
        </Title>
        <Text c="dimmed" fz="sm">
          Наведите камеру на QR абитуриента, чтобы отметить приход.
        </Text>
      </Stack>

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
          style={{ maxWidth: 360 }}
        />
      )}

      {!scanning && (
        <Button
          leftSection={<IconQrcode size={18} stroke={1.8} />}
          onClick={() => void startScanner()}
          loading={busy}
          style={{ alignSelf: 'flex-start', background: 'linear-gradient(135deg,#2c54ee,#1e3fcc)' }}
        >
          {outcome ? 'Сканировать ещё' : 'Начать сканирование'}
        </Button>
      )}

      <Paper withBorder radius="lg" p="md" style={{ display: scanning ? 'block' : 'none' }}>
        <Box id={READER_ID} style={{ width: '100%', maxWidth: 360, margin: '0 auto' }} />
        <Group justify="center" mt="md">
          <Button variant="default" onClick={() => void stopScanner()}>
            Остановить
          </Button>
        </Group>
      </Paper>

      {outcome?.kind === 'ok' && <ResultCard result={outcome.result} />}
      {outcome?.kind === 'error' && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
          {outcome.message}
        </Alert>
      )}
    </Stack>
  )
}

function ResultCard({ result }: { result: CheckinResult }) {
  const already = result.already_checked_in
  return (
    <Paper withBorder radius="lg" p="lg" style={{ borderColor: already ? '#f59e0b' : '#10b981' }}>
      <Group gap="md" align="flex-start" wrap="nowrap">
        <ThemeIcon color={already ? 'orange' : 'teal'} size={48} radius="md" variant="light">
          {already ? (
            <IconAlertTriangle size={28} stroke={2} />
          ) : (
            <IconCheck size={28} stroke={2} />
          )}
        </ThemeIcon>
        <Stack gap={2}>
          <Text fw={700} fz="lg" style={{ color: '#0f172a' }}>
            {already ? 'Уже отмечен ранее' : 'Отмечен — приход зафиксирован'}
          </Text>
          <Text fz="sm" style={{ color: '#0f172a' }}>
            {result.user_name}
          </Text>
          <Text fz="sm" c="dimmed">
            {result.event_title}
          </Text>
          {result.short_code && (
            <Text fz="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
              Код: {result.short_code}
            </Text>
          )}
        </Stack>
      </Group>
    </Paper>
  )
}
