import {
  Badge,
  Button,
  Card,
  Container,
  FileInput,
  Group,
  Radio,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconPhoto, IconSend } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import {
  type AdCampaign,
  type AdCampaignStatus,
  createAdCampaign,
  listAdCampaigns,
  uploadBroadcastImage,
} from '../api'

const STATUS_META: Record<AdCampaignStatus, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'gray' },
  scheduled: { label: 'Запланирована', color: 'blue' },
  sending: { label: 'Отправляется', color: 'yellow' },
  sent: { label: 'Отправлена', color: 'teal' },
}

function fmt(dt: string | null): string {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

export function AdBroadcastsPage() {
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [mode, setMode] = useState<'now' | 'schedule'>('now')
  const [sendAt, setSendAt] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try {
      setCampaigns(await listAdCampaigns())
    } catch {
      notifications.show({ color: 'red', message: 'Не удалось загрузить рассылки' })
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function submit() {
    if (!title.trim()) {
      notifications.show({ color: 'red', message: 'Укажите заголовок' })
      return
    }
    if (mode === 'schedule' && !sendAt) {
      notifications.show({ color: 'red', message: 'Укажите время отправки' })
      return
    }
    setBusy(true)
    try {
      let imagePath: string | null = null
      if (image) {
        imagePath = (await uploadBroadcastImage(image)).path
      }
      const created = await createAdCampaign({
        title: title.trim(),
        body: body.trim() || null,
        image_path: imagePath,
        send_now: mode === 'now',
        send_at: mode === 'schedule' ? new Date(sendAt).toISOString() : null,
      })
      if (created.status === 'sent') {
        notifications.show({
          color: 'teal',
          title: 'Отправлено',
          message: `Доставлено ${created.delivered} из ${created.recipients_total} (ошибок: ${created.errors})`,
        })
      } else if (created.status === 'scheduled') {
        notifications.show({
          color: 'blue',
          title: 'Запланировано',
          message: `Отправится ${fmt(created.send_at)}`,
        })
      }
      setTitle('')
      setBody('')
      setImage(null)
      setSendAt('')
      setMode('now')
      await refresh()
    } catch {
      notifications.show({ color: 'red', message: 'Не удалось создать рассылку' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Container size="lg" py="md">
      <Title order={2} mb="xs">
        Рекламные рассылки
      </Title>
      <Text c="dimmed" fz="sm" mb="lg">
        Сообщение получат все пользователи бота. Заголовок обязателен, описание и фото — по желанию.
      </Text>

      <Card withBorder radius="md" p="lg" mb="xl">
        <Stack gap="md">
          <TextInput
            label="Заголовок"
            placeholder="Например: День открытых дверей 15 июня!"
            required
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            maxLength={160}
          />
          <Textarea
            label="Описание"
            description="Можно не указывать"
            placeholder="Текст поста…"
            autosize
            minRows={3}
            maxRows={8}
            value={body}
            onChange={(e) => setBody(e.currentTarget.value)}
          />
          <FileInput
            label="Фото"
            description="Опционально, до 10 МБ"
            placeholder="Выбрать изображение"
            leftSection={<IconPhoto size={16} />}
            accept="image/*"
            clearable
            value={image}
            onChange={setImage}
          />
          <Radio.Group
            label="Когда отправить"
            value={mode}
            onChange={(v) => setMode(v as 'now' | 'schedule')}
          >
            <Group mt="xs">
              <Radio value="now" label="Сейчас" />
              <Radio value="schedule" label="Запланировать" />
            </Group>
          </Radio.Group>
          {mode === 'schedule' && (
            <TextInput
              type="datetime-local"
              label="Время отправки"
              value={sendAt}
              onChange={(e) => setSendAt(e.currentTarget.value)}
              w={260}
            />
          )}
          <Group>
            <Button
              leftSection={<IconSend size={16} />}
              loading={busy}
              onClick={submit}
              color="brand"
            >
              {mode === 'now' ? 'Отправить всем' : 'Запланировать'}
            </Button>
          </Group>
        </Stack>
      </Card>

      <Title order={4} mb="sm">
        История
      </Title>
      <Card withBorder radius="md" p={0}>
        <Table verticalSpacing="sm" horizontalSpacing="md">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Заголовок</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Доставлено</Table.Th>
              <Table.Th>Отправка</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {campaigns.map((c) => {
              const meta = STATUS_META[c.status]
              return (
                <Table.Tr key={c.id}>
                  <Table.Td>
                    <Text fw={500}>{c.title}</Text>
                    {c.image_path && (
                      <Text fz="xs" c="dimmed">
                        с фото
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Badge color={meta.color} variant="light">
                      {meta.label}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {c.status === 'sent'
                      ? `${c.delivered}/${c.recipients_total}${c.errors ? ` (ошибок ${c.errors})` : ''}`
                      : '—'}
                  </Table.Td>
                  <Table.Td>{fmt(c.sent_at ?? c.send_at)}</Table.Td>
                </Table.Tr>
              )
            })}
            {campaigns.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={4}>
                  <Text c="dimmed" ta="center" py="md">
                    Пока нет рассылок
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Card>
    </Container>
  )
}
