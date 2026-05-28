import {
  Badge,
  Button,
  Flex,
  Loader,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconSend } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import { api } from '../api'

interface Broadcast {
  id: string
  event_id: string
  kind: string
  audience: string
  status: string
  extra_text: string | null
  custom_topic_label: string | null
  send_at: string | null
  sent_at: string | null
  created_at: string
  delivered: number
  muted: number
  errors: number
}

const KIND_LABELS: Record<string, string> = {
  time_change: 'Изменение времени',
  venue_change: 'Изменение места',
  link_update: 'Обновление ссылки',
  reminder_24h: 'Напоминание за сутки',
  reminder_1h: 'Напоминание за час',
  other: 'Другое',
}

const AUDIENCE_LABELS: Record<string, string> = {
  confirmed: 'Подтверждённым',
  waitlist: 'Листу ожидания',
  all_active: 'Всем активным',
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  scheduled: 'Запланирована',
  sending: 'Отправляется',
  sent: 'Отправлена',
  cancelled: 'Отменена',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'gray',
  scheduled: 'blue',
  sending: 'orange',
  sent: 'teal',
  cancelled: 'red',
}

const KIND_OPTIONS = [
  { value: 'time_change', label: 'Изменение времени' },
  { value: 'venue_change', label: 'Изменение места' },
  { value: 'link_update', label: 'Обновление ссылки' },
  { value: 'other', label: 'Другое (свой заголовок)' },
]

const AUDIENCE_OPTIONS = [
  { value: 'confirmed', label: 'Подтверждённым' },
  { value: 'waitlist', label: 'Листу ожидания' },
  { value: 'all_active', label: 'Всем активным' },
]

function formatSentAt(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function DeliveryLine({ delivered, muted, errors }: Pick<Broadcast, 'delivered' | 'muted' | 'errors'>) {
  const parts: string[] = []
  if (delivered > 0) parts.push(`Доставлено ${delivered}`)
  if (muted > 0) parts.push(`Заглушено ${muted}`)
  if (errors > 0) parts.push(`Ошибок ${errors}`)
  if (parts.length === 0) return null
  return (
    <Text fz="xs" c="dimmed">
      {parts.join(' · ')}
    </Text>
  )
}

export function BroadcastsTab({ eventId }: { eventId: string }) {
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [sending, setSending] = useState(false)

  const [kind, setKind] = useState<string | null>(null)
  const [audience, setAudience] = useState<string | null>(null)
  const [extraText, setExtraText] = useState('')
  const [customTopic, setCustomTopic] = useState('')

  function fetchList() {
    setListLoading(true)
    api
      .get<Broadcast[]>(`/api/admin/events/${eventId}/broadcasts`)
      .then((r) => setBroadcasts(r.data))
      .catch(() =>
        notifications.show({
          color: 'red',
          title: 'Не удалось загрузить рассылки',
          message: 'Проверьте соединение и обновите страницу',
        }),
      )
      .finally(() => setListLoading(false))
  }

  useEffect(() => {
    fetchList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId])

  async function handleSend() {
    if (!kind) {
      notifications.show({ color: 'orange', title: 'Выберите тип рассылки', message: '' })
      return
    }
    if (!audience) {
      notifications.show({ color: 'orange', title: 'Выберите получателей', message: '' })
      return
    }
    if (!extraText.trim()) {
      notifications.show({ color: 'orange', title: 'Введите текст сообщения', message: '' })
      return
    }
    if (kind === 'other' && !customTopic.trim()) {
      notifications.show({ color: 'orange', title: 'Заполните заголовок «Другое»', message: '' })
      return
    }

    setSending(true)
    try {
      const { data } = await api.post<Broadcast>(
        `/api/admin/events/${eventId}/broadcasts`,
        {
          kind,
          audience,
          extra_text: extraText.trim(),
          custom_topic_label: kind === 'other' ? customTopic.trim() : null,
          send_now: true,
        },
      )
      const isScheduled = data.status === 'scheduled'
      notifications.show({
        color: 'teal',
        title: isScheduled ? 'Рассылка поставлена в очередь' : 'Рассылка отправлена',
        message: `${KIND_LABELS[kind] ?? kind} → ${AUDIENCE_LABELS[audience] ?? audience}`,
        autoClose: 3000,
      })
      setExtraText('')
      setCustomTopic('')
      fetchList()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : detail
          ? JSON.stringify(detail)
          : 'Попробуйте ещё раз'
      notifications.show({ color: 'red', title: 'Ошибка отправки', message })
    } finally {
      setSending(false)
    }
  }

  return (
    <Stack gap="lg">
      {/* Compose form */}
      <Paper p="xl" radius="lg" withBorder>
        <Stack gap="md">
          <Stack gap={2}>
            <Title order={4} style={{ color: '#0f172a' }}>Новая рассылка</Title>
            <Text fz="xs" c="dimmed">Разошлёт сообщение в MAX выбранной аудитории</Text>
          </Stack>

          <Flex gap="md" wrap="wrap">
            <Select
              label="Тип"
              placeholder="Выберите тип"
              data={KIND_OPTIONS}
              value={kind}
              onChange={setKind}
              style={{ flex: 1, minWidth: 200 }}
            />
            <Select
              label="Кому"
              placeholder="Выберите аудиторию"
              data={AUDIENCE_OPTIONS}
              value={audience}
              onChange={setAudience}
              style={{ flex: 1, minWidth: 200 }}
            />
          </Flex>

          {kind === 'other' && (
            <TextInput
              label="Свой заголовок"
              placeholder="Например, «Перенос мастер-класса»"
              description="Заменит стандартный префикс — увидит каждый получатель"
              maxLength={80}
              value={customTopic}
              onChange={(e) => setCustomTopic(e.currentTarget.value)}
            />
          )}

          <Textarea
            label="Текст сообщения"
            placeholder="Введите текст уведомления для участников…"
            autosize
            minRows={3}
            maxRows={8}
            value={extraText}
            onChange={(e) => setExtraText(e.currentTarget.value)}
          />

          <Flex justify="flex-end">
            <Button
              leftSection={<IconSend size={16} stroke={1.8} />}
              loading={sending}
              onClick={handleSend}
              style={{ background: 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)' }}
            >
              Отправить сейчас
            </Button>
          </Flex>
        </Stack>
      </Paper>

      {/* Broadcasts list */}
      <Stack gap="md">
        <Stack gap={2}>
          <Title order={5} style={{ color: '#0f172a' }}>История рассылок</Title>
          <Text fz="xs" c="dimmed">Рассылки, отправленные для этого мероприятия</Text>
        </Stack>

        {listLoading ? (
          <Flex justify="center" py="xl">
            <Loader />
          </Flex>
        ) : broadcasts.length === 0 ? (
          <Paper p="xl" withBorder radius="lg">
            <Stack align="center" gap="xs">
              <Text c="dimmed" ta="center">Рассылок ещё не было.</Text>
              <Text fz="xs" c="dimmed" ta="center">
                Используйте форму выше, чтобы отправить первое уведомление участникам.
              </Text>
            </Stack>
          </Paper>
        ) : (
          broadcasts.map((b) => (
            <Paper key={b.id} p="lg" radius="lg" withBorder>
              <Flex justify="space-between" align="flex-start" gap="md" wrap="wrap">
                <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
                  <Flex align="center" gap="sm" wrap="wrap">
                    <Text fw={500} fz="sm" style={{ color: '#0f172a' }}>
                      {b.kind === 'other' && b.custom_topic_label
                        ? b.custom_topic_label
                        : (KIND_LABELS[b.kind] ?? b.kind)}
                    </Text>
                    <Badge
                      size="sm"
                      color={STATUS_COLORS[b.status] ?? 'gray'}
                      variant="light"
                    >
                      {STATUS_LABELS[b.status] ?? b.status}
                    </Badge>
                  </Flex>
                  <Text fz="xs" c="dimmed">
                    {AUDIENCE_LABELS[b.audience] ?? b.audience}
                    {b.sent_at && ` · ${formatSentAt(b.sent_at)}`}
                  </Text>
                  {b.extra_text && (
                    <Text fz="sm" c="dimmed" lineClamp={2}>
                      {b.extra_text}
                    </Text>
                  )}
                  <DeliveryLine delivered={b.delivered} muted={b.muted} errors={b.errors} />
                </Stack>
              </Flex>
            </Paper>
          ))
        )}
      </Stack>
    </Stack>
  )
}
