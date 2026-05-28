import {
  ActionIcon, Autocomplete, Box, Button, Container, Drawer, Flex, Group, Loader, Menu, NumberInput,
  Paper, Select, Stack, Switch, Tabs, Text, Textarea, TextInput, Title,
} from '@mantine/core'
import { DateTimePicker } from '@mantine/dates'
import { useForm } from '@mantine/form'
import { modals } from '@mantine/modals'
import { notifications } from '@mantine/notifications'
import {
  IconArrowBackUp, IconArrowLeft, IconCalendarEvent, IconCheck,
  IconCopy, IconDeviceFloppy, IconDotsVertical, IconForms, IconQrcode, IconShare, IconShieldCheck, IconSpeakerphone,
  IconTrash, IconUsers, IconX,
} from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useBlocker, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { BroadcastsTab } from '../components/BroadcastsTab'
import { RegistrationsTable } from '../components/RegistrationsTable'
import { StatusBadge } from '../components/StatusBadge'
import { FieldsTab } from '../components/form-constructor/FieldsTab'

interface EventFull {
  id: string
  title: string
  description: string | null
  event_type: string
  custom_type_label: string | null
  format: 'offline' | 'online' | 'hybrid'
  online_url: string | null
  late_cancellation_policy: 'forbid' | 'allow_with_mark'
  starts_at: string
  duration_minutes: number
  location: string | null
  capacity: number | null
  waitlist_enabled: boolean
  moderation_required: boolean
  registration_opens_at: string | null
  registration_closes_at: string | null
  status: string
  reminder_offsets_minutes: number[]
}

interface FormValues {
  title: string
  description: string
  event_type: string
  custom_type_label: string
  format: 'offline' | 'online' | 'hybrid'
  online_url: string
  late_cancellation_policy: 'forbid' | 'allow_with_mark'
  starts_at: Date
  duration_minutes: number
  location: string
  capacity: number | null
  waitlist_enabled: boolean
  moderation_required: boolean
  registration_opens_at: Date | null
  registration_closes_at: Date | null
  reminder_offsets_minutes: number[]
}

const EVENT_TYPES = [
  { value: 'open_day', label: 'День открытых дверей' },
  { value: 'master_class', label: 'Мастер-класс' },
  { value: 'olympiad', label: 'Олимпиада' },
  { value: 'consultation', label: 'Консультация' },
  { value: 'other', label: 'Другое (свой тип)' },
]

const FORMAT_OPTIONS = [
  { value: 'offline', label: '🏛 Очно' },
  { value: 'online', label: '💻 Онлайн' },
  { value: 'hybrid', label: '🌐 Гибрид' },
]

const POLICY_OPTIONS = [
  { value: 'forbid', label: 'Запретить отмену после начала' },
  { value: 'allow_with_mark', label: 'Разрешить с пометкой «поздняя отмена»' },
]

const REMINDER_PRESETS = [
  { value: 10080, label: 'За неделю' },
  { value: 1440,  label: 'За 24 часа' },
  { value: 60,    label: 'За час' },
  { value: 15,    label: 'За 15 минут' },
]

const injectStyles = (() => {
  let done = false
  return () => {
    if (done) return
    done = true
    const s = document.createElement('style')
    s.textContent = `
      @keyframes editor-fadeUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
      }
    `
    document.head.appendChild(s)
  }
})()

const TEMPLATE_DEFAULTS: Record<string, Partial<FormValues>> = {
  open_day: {
    title: 'День открытых дверей',
    description: 'Покажем кампус, расскажем о программах, ответим на вопросы.',
    event_type: 'open_day',
    duration_minutes: 180,
    capacity: 200,
  },
  master_class: {
    title: 'Мастер-класс',
    description: 'Практическое занятие от преподавателя кафедры.',
    event_type: 'master_class',
    duration_minutes: 90,
    capacity: 30,
  },
  olympiad: {
    title: 'Олимпиада',
    description: 'Олимпиада для школьников. Призёрам — преимущества при поступлении.',
    event_type: 'olympiad',
    duration_minutes: 180,
    capacity: 100,
    waitlist_enabled: false,
  },
  consultation: {
    title: 'Консультация',
    description: 'Личная или групповая консультация по программам и поступлению.',
    event_type: 'consultation',
    duration_minutes: 60,
    capacity: 10,
    format: 'online',
  },
}

function defaultsFromEvent(e: EventFull | null, template?: string | null): FormValues {
  if (!e) {
    const base: FormValues = {
      title: '',
      description: '',
      event_type: 'other',
      custom_type_label: '',
      format: 'offline',
      online_url: '',
      late_cancellation_policy: 'forbid',
      starts_at: new Date(Date.now() + 7 * 86400000),
      duration_minutes: 60,
      location: '',
      capacity: 50,
      waitlist_enabled: true,
      moderation_required: false,
      registration_opens_at: null,
      registration_closes_at: null,
      reminder_offsets_minutes: [1440, 60],
    }
    if (template && TEMPLATE_DEFAULTS[template]) {
      return { ...base, ...TEMPLATE_DEFAULTS[template] }
    }
    return base
  }
  return {
    title: e.title,
    description: e.description ?? '',
    event_type: e.event_type,
    custom_type_label: e.custom_type_label ?? '',
    format: e.format ?? 'offline',
    online_url: e.online_url ?? '',
    late_cancellation_policy: e.late_cancellation_policy ?? 'forbid',
    starts_at: new Date(e.starts_at),
    duration_minutes: e.duration_minutes,
    location: e.location ?? '',
    capacity: e.capacity,
    waitlist_enabled: e.waitlist_enabled,
    moderation_required: e.moderation_required,
    registration_opens_at: e.registration_opens_at ? new Date(e.registration_opens_at) : null,
    registration_closes_at: e.registration_closes_at ? new Date(e.registration_closes_at) : null,
    reminder_offsets_minutes: e.reminder_offsets_minutes ?? [],
  }
}

function buildPayload(v: FormValues) {
  return {
    title: v.title,
    description: v.description || null,
    event_type: v.event_type,
    custom_type_label: v.event_type === 'other' ? (v.custom_type_label || null) : null,
    format: v.format,
    online_url: v.format === 'offline' ? null : (v.online_url || null),
    late_cancellation_policy: v.late_cancellation_policy,
    starts_at: v.starts_at.toISOString(),
    duration_minutes: v.duration_minutes,
    location: v.location || null,
    capacity: v.capacity,
    waitlist_enabled: v.waitlist_enabled,
    moderation_required: v.moderation_required,
    registration_opens_at: v.registration_opens_at ? v.registration_opens_at.toISOString() : null,
    registration_closes_at: v.registration_closes_at ? v.registration_closes_at.toISOString() : null,
    reminder_offsets_minutes: v.reminder_offsets_minutes,
  }
}

/** Преобразует FastAPI error detail (string или array Pydantic-объектов) в строку. */
function formatApiError(detail: unknown, fallback = 'Попробуйте ещё раз'): string {
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e: any) => {
        const loc = Array.isArray(e?.loc) ? e.loc.filter((x: any) => x !== 'body').join('.') : ''
        const msg = e?.msg || 'invalid'
        return loc ? `${loc}: ${msg}` : msg
      })
      .join('; ')
  }
  try { return JSON.stringify(detail) } catch { return fallback }
}

export function EventEditorPage() {
  const { id } = useParams()
  const isNew = id === 'new'
  const [event, setEvent] = useState<EventFull | null>(null)
  const [loading, setLoading] = useState(!isNew)

  useEffect(() => {
    injectStyles()
    if (isNew) {
      setEvent(null)
      setLoading(false)
      return
    }
    setLoading(true)
    api.get<EventFull>(`/api/admin/events/${id}`)
      .then((r) => {
        setEvent(r.data)
        setLoading(false)
      })
      .catch(() => {
        notifications.show({
          color: 'red',
          title: 'Не удалось загрузить мероприятие',
          message: 'Проверьте соединение и обновите страницу',
        })
        setLoading(false)
      })
  }, [id, isNew])

  if (loading) {
    return (
      <Flex justify="center" align="center" h={300}>
        <Loader />
      </Flex>
    )
  }

  // Ключ форсит remount EditorBody при смене id или после первого save (когда event.id появляется)
  return <EditorBody key={event?.id ?? 'new'} initial={event} onChange={setEvent} />
}

function EditorBody({ initial, onChange }: { initial: EventFull | null; onChange: (e: EventFull) => void }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const template = searchParams.get('template')
  const isNew = initial === null
  const [event, setEventLocal] = useState<EventFull | null>(initial)
  const [saving, setSaving] = useState(false)
  const [tab, setTab] = useState<string | null>('basic')

  const initialValues = useMemo(() => defaultsFromEvent(initial, template), [initial, template])
  const form = useForm<FormValues>({
    mode: 'controlled',
    initialValues,
    validate: {
      title: (v) => (v.length >= 3 ? null : 'Минимум 3 символа'),
      duration_minutes: (v) => (v > 0 ? null : 'Больше 0'),
    },
  })

  const [locationSuggestions, setLocationSuggestions] = useState<string[]>([])
  useEffect(() => {
    api.get<{ location: string | null }[]>('/api/admin/events?limit=200').then((r) => {
      const counts = new Map<string, number>()
      for (const e of r.data) {
        const loc = (e.location || '').trim()
        if (loc) counts.set(loc, (counts.get(loc) ?? 0) + 1)
      }
      const top = Array.from(counts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([loc]) => loc)
      setLocationSuggestions(top)
    }).catch(() => {})
  }, [])

  const dirty = form.isDirty()

  const setEventBoth = useCallback((e: EventFull) => {
    setEventLocal(e)
    onChange(e)
  }, [onChange])

  const performSave = useCallback(async () => {
    if (form.validate().hasErrors) return
    setSaving(true)
    const payload = buildPayload(form.getValues())
    try {
      if (isNew) {
        const { data } = await api.post<EventFull>('/api/admin/events', payload)
        form.resetDirty()
        notifications.show({
          color: 'teal',
          title: 'Мероприятие создано',
          message: data.title,
          icon: <IconCheck size={18} stroke={2.4} />,
        })
        navigate(`/events/${data.id}`, { replace: true })
      } else {
        const { data } = await api.patch<EventFull>(`/api/admin/events/${event!.id}`, payload)
        setEventBoth(data)
        form.resetDirty()
        notifications.show({
          color: 'teal',
          title: 'Сохранено',
          message: data.title,
          icon: <IconCheck size={18} stroke={2.4} />,
          autoClose: 2200,
        })
      }
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Ошибка сохранения',
        message: formatApiError(e?.response?.data?.detail),
      })
    } finally {
      setSaving(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event?.id, isNew, navigate, setEventBoth])

  // beforeunload
  useEffect(() => {
    if (!dirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  // SPA-blocker для дочерней навигации — читаем dirty в момент навигации, не на рендере
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }: { currentLocation: { pathname: string }; nextLocation: { pathname: string } }) =>
      form.isDirty() && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    modals.openConfirmModal({
      title: 'Уйти без сохранения?',
      children: (
        <Stack gap="xs">
          <Text fz="sm">Несохранённые изменения будут потеряны.</Text>
        </Stack>
      ),
      labels: { confirm: 'Уйти без сохранения', cancel: 'Остаться' },
      confirmProps: { color: 'red' },
      onConfirm: () => blocker.proceed?.(),
      onCancel: () => blocker.reset?.(),
      onClose: () => blocker.reset?.(),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocker.state])

  function handleTabChange(next: string | null) {
    if (!dirty || next === tab) {
      setTab(next)
      return
    }
    modals.openConfirmModal({
      title: 'Переключить вкладку?',
      children: <Text fz="sm">Несохранённые изменения на текущей вкладке будут потеряны.</Text>,
      labels: { confirm: 'Переключить', cancel: 'Остаться' },
      confirmProps: { color: 'red' },
      onConfirm: () => {
        form.reset()
        setTab(next)
      },
    })
  }

  async function publish() {
    if (!event) return
    try {
      const { data } = await api.post<EventFull>(`/api/admin/events/${event.id}/publish`)
      setEventBoth(data)
      notifications.show({
        color: 'teal',
        title: 'Опубликовано',
        message: data.title,
        icon: <IconCheck size={18} stroke={2.4} />,
      })
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Не удалось опубликовать',
        message: formatApiError(e?.response?.data?.detail),
      })
    }
  }

  function confirmCancel() {
    if (!event) return
    modals.openConfirmModal({
      title: 'Отменить мероприятие?',
      children: (
        <Stack gap="xs">
          <Text fz="sm">
            Вы собираетесь отменить <strong>«{event.title}»</strong>.
          </Text>
          <Text fz="sm" c="dimmed">
            Регистрация закроется, всем confirmed-участникам стоит разослать уведомление. Действие можно откатить кнопкой «Восстановить».
          </Text>
        </Stack>
      ),
      labels: { confirm: 'Отменить мероприятие', cancel: 'Назад' },
      confirmProps: { color: 'red' },
      onConfirm: doCancel,
    })
  }

  async function doCancel() {
    if (!event) return
    try {
      const { data } = await api.post<EventFull>(`/api/admin/events/${event.id}/cancel`)
      setEventBoth(data)
      notifications.show({ color: 'orange', title: 'Мероприятие отменено', message: data.title })
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Не удалось отменить',
        message: formatApiError(e?.response?.data?.detail),
      })
    }
  }

  async function restore() {
    if (!event) return
    try {
      const { data } = await api.post<EventFull>(`/api/admin/events/${event.id}/restore`)
      setEventBoth(data)
      notifications.show({
        color: 'teal',
        title: 'Восстановлено',
        message: `${data.title} вернулось в черновик — можно редактировать и публиковать заново`,
        icon: <IconCheck size={18} stroke={2.4} />,
      })
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Не удалось восстановить',
        message: formatApiError(e?.response?.data?.detail),
      })
    }
  }

  async function duplicate() {
    if (!event) return
    try {
      const { data } = await api.post<EventFull>(`/api/admin/events/${event.id}/duplicate`)
      notifications.show({
        color: 'teal',
        title: 'Дубликат создан',
        message: data.title,
        icon: <IconCheck size={18} stroke={2.4} />,
      })
      navigate(`/events/${data.id}`)
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Не удалось скопировать',
        message: formatApiError(e?.response?.data?.detail),
      })
    }
  }

  function confirmDelete() {
    if (!event) return
    modals.openConfirmModal({
      title: 'Удалить черновик?',
      children: (
        <Stack gap="xs">
          <Text fz="sm">
            Черновик <strong>«{event.title}»</strong> будет удалён без возможности восстановления.
          </Text>
          <Text fz="sm" c="dimmed">
            Действие необратимо. Для опубликованных мероприятий используйте «Отменить».
          </Text>
        </Stack>
      ),
      labels: { confirm: 'Удалить', cancel: 'Назад' },
      confirmProps: { color: 'red' },
      onConfirm: doDelete,
    })
  }

  async function doDelete() {
    if (!event) return
    try {
      await api.delete(`/api/admin/events/${event.id}`)
      notifications.show({ color: 'gray', title: 'Удалено', message: event.title })
      navigate('/events')
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Не удалось удалить',
        message: formatApiError(e?.response?.data?.detail),
      })
    }
  }

  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const [autoSaving, setAutoSaving] = useState(false)
  const [, tick] = useState(0)
  const [shareOpen, setShareOpen] = useState(false)

  const silentSave = useCallback(async () => {
    if (!event || isNew || saving || autoSaving) return
    if (form.validate().hasErrors) return
    setAutoSaving(true)
    const payload = buildPayload(form.getValues())
    try {
      const { data } = await api.patch<EventFull>(`/api/admin/events/${event.id}`, payload)
      setEventBoth(data)
      form.resetDirty()
      setLastSavedAt(new Date())
    } catch {
      // тихо игнорируем — пользователь увидит «Не сохранено» и сможет нажать Сохранить вручную
    } finally {
      setAutoSaving(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event?.id, isNew, saving, autoSaving])

  useEffect(() => {
    if (isNew || !dirty) return
    const t = setTimeout(() => { void silentSave() }, 2000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(form.getValues()), dirty, isNew])

  useEffect(() => {
    if (!lastSavedAt) return
    const i = setInterval(() => tick((x) => x + 1), 15_000)
    return () => clearInterval(i)
  }, [lastSavedAt])

  const dirtyBadge = useMemo(() => {
    if (isNew) return null
    if (autoSaving) {
      return (
        <Flex gap={6} align="center">
          <Loader size={10} />
          <Text fz="xs" c="dimmed">Сохраняем…</Text>
        </Flex>
      )
    }
    if (dirty) {
      return (
        <Flex gap={6} align="center">
          <Box w={6} h={6} style={{ borderRadius: '50%', background: '#f59e0b' }} />
          <Text fz="xs" c="dimmed">Не сохранено</Text>
        </Flex>
      )
    }
    if (lastSavedAt) {
      const secs = Math.round((Date.now() - lastSavedAt.getTime()) / 1000)
      const label =
        secs < 5 ? 'Сохранено' :
        secs < 60 ? `Сохранено ${secs} с назад` :
        `Сохранено ${Math.round(secs / 60)} мин назад`
      return (
        <Flex gap={6} align="center">
          <Box w={6} h={6} style={{ borderRadius: '50%', background: '#16a34a' }} />
          <Text fz="xs" c="dimmed">{label}</Text>
        </Flex>
      )
    }
    return null
  }, [dirty, isNew, autoSaving, lastSavedAt])

  return (
    <Stack gap="lg" style={{ animation: 'editor-fadeUp 0.3s ease both' }}>
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="md">
        <Flex align="center" gap="md">
          <ActionIcon variant="subtle" size="lg" onClick={() => navigate('/events')}>
            <IconArrowLeft size={20} stroke={1.8} />
          </ActionIcon>
          <Stack gap={4}>
            <Title order={2} style={{ color: '#0f172a' }}>
              {isNew ? 'Новое мероприятие' : event?.title || '…'}
            </Title>
            {!isNew && event && (
              <Flex gap="sm" align="center" wrap="wrap">
                <StatusBadge status={event.status} />
                <Text fz="xs" c="dimmed">id: {event.id.slice(0, 8)}</Text>
                {dirtyBadge}
              </Flex>
            )}
          </Stack>
        </Flex>
        <Group>
          {event && event.status === 'published' && !isNew && (
            <Button
              variant="light"
              color="teal"
              leftSection={<IconQrcode size={16} stroke={2} />}
              onClick={() => navigate(`/events/${event.id}/checkin`)}
            >
              Контроль входа
            </Button>
          )}
          {event && event.status === 'draft' && (
            <Button variant="light" color="teal" leftSection={<IconCheck size={16} stroke={2} />} onClick={publish}>
              Опубликовать
            </Button>
          )}
          {event && event.status === 'published' && (
            <Button variant="light" color="red" leftSection={<IconX size={16} stroke={2} />} onClick={confirmCancel}>
              Отменить
            </Button>
          )}
          {event && event.status === 'cancelled' && (
            <Button variant="light" color="teal" leftSection={<IconArrowBackUp size={16} stroke={2} />} onClick={restore}>
              Восстановить
            </Button>
          )}
          <Button
            leftSection={<IconDeviceFloppy size={16} stroke={2} />}
            loading={saving}
            onClick={() => performSave()}
            style={{ background: 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)' }}
          >
            Сохранить
          </Button>
          {!isNew && event && (
            <Menu shadow="md" position="bottom-end" width={220}>
              <Menu.Target>
                <ActionIcon variant="default" size="lg">
                  <IconDotsVertical size={18} stroke={1.8} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<IconCopy size={16} stroke={1.8} />} onClick={duplicate}>
                  Дублировать
                </Menu.Item>
                {event.status === 'published' && (
                  <Menu.Item
                    leftSection={<IconShare size={16} stroke={1.8} />}
                    onClick={() => setShareOpen(true)}
                  >
                    Поделиться QR-приглашением
                  </Menu.Item>
                )}
                {event.status === 'draft' && (
                  <>
                    <Menu.Divider />
                    <Menu.Item
                      color="red"
                      leftSection={<IconTrash size={16} stroke={1.8} />}
                      onClick={confirmDelete}
                    >
                      Удалить черновик
                    </Menu.Item>
                  </>
                )}
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>
      </Flex>

      <Tabs value={tab} onChange={handleTabChange} variant="default">
        <Tabs.List>
          <Tabs.Tab value="basic" leftSection={<IconCalendarEvent size={16} stroke={1.8} />}>Основное</Tabs.Tab>
          <Tabs.Tab value="fields" leftSection={<IconForms size={16} stroke={1.8} />} disabled={isNew}>Поля формы</Tabs.Tab>
          <Tabs.Tab value="controllers" leftSection={<IconShieldCheck size={16} stroke={1.8} />} disabled={isNew}>Контролёры</Tabs.Tab>
          <Tabs.Tab value="regs" leftSection={<IconUsers size={16} stroke={1.8} />} disabled={isNew}>Записи</Tabs.Tab>
          <Tabs.Tab value="broadcasts" leftSection={<IconSpeakerphone size={16} stroke={1.8} />} disabled={isNew}>Рассылки</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="basic" pt="lg">
          <Container size={760} px={0}>
            <Stack gap="lg">
              <Paper p="xl" radius="lg" withBorder>
                <Stack gap="md">
                  <Stack gap={2}>
                    <Title order={4} style={{ color: '#0f172a' }}>Основная информация</Title>
                    <Text fz="xs" c="dimmed">Название, описание, дата, тип мероприятия</Text>
                  </Stack>
                  <TextInput
                    label="Название"
                    placeholder="День открытых дверей РТУ МИРЭА"
                    required
                    {...form.getInputProps('title')}
                  />
                  <Textarea
                    label="Описание"
                    placeholder="Опишите мероприятие — что будет, для кого, что взять с собой"
                    autosize
                    minRows={3}
                    maxRows={8}
                    {...form.getInputProps('description')}
                  />
                  <Group grow>
                    <Select label="Тип" data={EVENT_TYPES} {...form.getInputProps('event_type')} />
                    <Select label="Формат" data={FORMAT_OPTIONS} {...form.getInputProps('format')} />
                  </Group>
                  {form.values.event_type === 'other' && (
                    <TextInput
                      label="Свой тип мероприятия"
                      placeholder="Например, «Профориентационная игра»"
                      maxLength={80}
                      description="Этот текст увидят абитуриенты в каталоге вместо общего «Мероприятие»"
                      {...form.getInputProps('custom_type_label')}
                    />
                  )}
                  <Group grow>
                    <DateTimePicker
                      label="Начало"
                      required
                      valueFormat="DD MMMM YYYY · HH:mm"
                      {...form.getInputProps('starts_at')}
                    />
                    <NumberInput
                      label="Длительность (минут)"
                      min={5}
                      max={1440}
                      {...form.getInputProps('duration_minutes')}
                    />
                  </Group>
                  {form.values.format !== 'online' && (
                    <Autocomplete
                      label="Место проведения"
                      placeholder="Например, проспект Вернадского, 78"
                      data={locationSuggestions}
                      limit={5}
                      {...form.getInputProps('location')}
                    />
                  )}
                  {form.values.format !== 'offline' && (
                    <TextInput
                      label="Ссылка на подключение"
                      placeholder="https://meet.example.com/abc"
                      description="Показывается участникам после подтверждения записи"
                      {...form.getInputProps('online_url')}
                    />
                  )}
                </Stack>
              </Paper>

              <Paper p="xl" radius="lg" withBorder>
                <Stack gap="md">
                  <Stack gap={2}>
                    <Title order={4} style={{ color: '#0f172a' }}>Регистрация</Title>
                    <Text fz="xs" c="dimmed">Лимит мест, лист ожидания, окно регистрации</Text>
                  </Stack>
                  <Group grow>
                    <NumberInput
                      label="Лимит мест"
                      description="Оставьте пустым для безлимитного"
                      min={0}
                      {...form.getInputProps('capacity')}
                    />
                    <Select
                      label="Политика отмены"
                      description="Что разрешено после начала мероприятия"
                      data={POLICY_OPTIONS}
                      {...form.getInputProps('late_cancellation_policy')}
                    />
                  </Group>
                  <Group grow>
                    <DateTimePicker
                      label="Открытие регистрации"
                      description="Опционально, до этого момента кнопка «Записаться» скрыта"
                      valueFormat="DD MMMM · HH:mm"
                      clearable
                      {...form.getInputProps('registration_opens_at')}
                    />
                    <DateTimePicker
                      label="Закрытие регистрации"
                      description="Опционально"
                      valueFormat="DD MMMM · HH:mm"
                      clearable
                      {...form.getInputProps('registration_closes_at')}
                    />
                  </Group>
                  <Switch
                    label="Лист ожидания"
                    description="Когда мест нет — записывать в очередь, автопромоушен при отмене"
                    {...form.getInputProps('waitlist_enabled', { type: 'checkbox' })}
                  />
                  <Switch
                    label="Модерация записей"
                    description="Запись становится подтверждённой только после одобрения админом"
                    {...form.getInputProps('moderation_required', { type: 'checkbox' })}
                  />
                </Stack>
              </Paper>

              <Paper p="xl" radius="lg" withBorder>
                <Stack gap="md">
                  <Stack gap={2}>
                    <Title order={4} style={{ color: '#0f172a' }}>Напоминания</Title>
                    <Text fz="xs" c="dimmed">Бот разошлёт напоминания всем confirmed-участникам</Text>
                  </Stack>
                  <Flex gap="xs" wrap="wrap">
                    {REMINDER_PRESETS.map((p) => {
                      const active = form.values.reminder_offsets_minutes.includes(p.value)
                      return (
                        <Box
                          key={p.value}
                          onClick={() => {
                            const cur = form.values.reminder_offsets_minutes
                            form.setFieldValue(
                              'reminder_offsets_minutes',
                              active ? cur.filter((x) => x !== p.value) : [...cur, p.value].sort((a, b) => b - a),
                            )
                          }}
                          style={{
                            cursor: 'pointer',
                            padding: '8px 16px',
                            borderRadius: 9999,
                            border: `1.5px solid ${active ? '#2c54ee' : 'var(--color-neutral-200)'}`,
                            background: active ? 'rgba(44,84,238,0.08)' : 'transparent',
                            color: active ? '#2c54ee' : '#475569',
                            fontWeight: 500,
                            fontSize: 14,
                            userSelect: 'none',
                            transition: 'all 0.12s ease',
                          }}
                        >
                          {p.label}
                        </Box>
                      )
                    })}
                  </Flex>
                </Stack>
              </Paper>

            </Stack>
          </Container>
        </Tabs.Panel>

        <Tabs.Panel value="fields" pt="lg">
          {event ? <FieldsTab eventId={event.id} /> : null}
        </Tabs.Panel>

        <Tabs.Panel value="controllers" pt="lg">
          <Container size={760} px={0}>
            {event && !isNew ? <ControllersBlock eventId={event.id} /> : null}
          </Container>
        </Tabs.Panel>

        <Tabs.Panel value="regs" pt="lg">
          {event ? <RegistrationsTable eventId={event.id} /> : null}
        </Tabs.Panel>

        <Tabs.Panel value="broadcasts" pt="lg">
          {event ? <BroadcastsTab eventId={event.id} /> : null}
        </Tabs.Panel>
      </Tabs>

      <ShareQrDrawer
        eventId={event?.id ?? null}
        eventTitle={event?.title ?? ''}
        opened={shareOpen}
        onClose={() => setShareOpen(false)}
      />
    </Stack>
  )
}

function ShareQrDrawer({
  eventId, eventTitle, opened, onClose,
}: {
  eventId: string | null
  eventTitle: string
  opened: boolean
  onClose: () => void
}) {
  const url = eventId ? `/api/admin/events/${eventId}/share-qr.png` : ''
  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="lg"
      title={<Title order={4}>QR-приглашение</Title>}
      padding="lg"
      overlayProps={{ opacity: 0.4, blur: 2 }}
    >
      <Stack gap="md" align="center">
        <Text fw={600} ta="center">{eventTitle}</Text>
        {eventId && (
          <Box
            style={{
              padding: 24, background: '#fff', borderRadius: 16,
              border: '1px solid var(--color-neutral-200)',
              boxShadow: '0 2px 12px rgba(15,23,42,0.08)',
            }}
          >
            <img src={url} alt="QR" style={{ width: 320, height: 320, imageRendering: 'pixelated' }} />
          </Box>
        )}
        <Text fz="sm" c="dimmed" ta="center" style={{ maxWidth: 360 }}>
          Распечатайте и разместите на афишах. Абитуриент сканирует — попадает
          сразу на карточку мероприятия в боте.
        </Text>
        <Button
          variant="default"
          leftSection={<IconShare size={16} stroke={1.8} />}
          onClick={() => {
            const a = document.createElement('a')
            a.href = url
            a.download = `qr-invite-${eventId?.slice(0, 8)}.png`
            a.click()
          }}
        >
          Скачать PNG
        </Button>
      </Stack>
    </Drawer>
  )
}

function ControllersBlock({ eventId }: { eventId: string }) {
  const [controllers, setControllers] = useState<{ admin_id: string; email: string; full_name: string | null }[] | null>(null)
  const [allControllers, setAllControllers] = useState<{ id: string; email: string; full_name: string | null }[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const { data } = await api.get<{ admin_id: string; email: string; full_name: string | null }[]>(
      `/api/admin/events/${eventId}/controllers`,
    )
    setControllers(data)
  }, [eventId])

  useEffect(() => {
    void load()
    api
      .get<{ web_admins: { id: string; email: string; full_name: string | null; role: string }[] }>('/api/admin/team')
      .then((r) => setAllControllers(r.data.web_admins.filter((a) => a.role === 'controller')))
      .catch(() => {})
  }, [load])

  const assign = async () => {
    if (!selected) return
    setBusy(true)
    try {
      await api.post(`/api/admin/events/${eventId}/controllers`, { admin_id: selected })
      setSelected(null)
      await load()
    } finally {
      setBusy(false)
    }
  }

  const unassign = async (id: string) => {
    setBusy(true)
    try {
      await api.delete(`/api/admin/events/${eventId}/controllers/${id}`)
      await load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper p="xl" radius="lg" withBorder>
      <Stack gap="md">
        <Stack gap={2}>
          <Title order={4} style={{ color: '#0f172a' }}>Контролёры</Title>
          <Text fz="xs" c="dimmed">Кто может отмечать приход на это мероприятие</Text>
        </Stack>
        <Group>
          <Select
            placeholder="Выберите контролёра"
            data={allControllers
              .filter((a) => !controllers?.some((c) => c.admin_id === a.id))
              .map((c) => ({ value: c.id, label: c.full_name || c.email }))}
            value={selected}
            onChange={setSelected}
            style={{ flex: 1 }}
            searchable
            nothingFoundMessage="Нет свободных контролёров"
          />
          <Button onClick={() => void assign()} disabled={!selected || busy}>
            Назначить
          </Button>
        </Group>
        {controllers === null ? (
          <Text c="dimmed">Загрузка…</Text>
        ) : controllers.length === 0 ? (
          <Text c="dimmed">Никто не назначен</Text>
        ) : (
          <Stack gap="xs">
            {controllers.map((c) => (
              <Group key={c.admin_id} justify="space-between">
                <Text>{c.full_name || c.email}</Text>
                <Button
                  size="xs"
                  color="red"
                  variant="subtle"
                  onClick={() => void unassign(c.admin_id)}
                  disabled={busy}
                >
                  Снять
                </Button>
              </Group>
            ))}
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
