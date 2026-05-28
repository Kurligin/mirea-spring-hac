import { Alert, Button, Flex, Grid, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle, IconDeviceFloppy, IconPlus } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import { api } from '../../api'

import { FieldDraft } from './types'
import { FieldEditor } from './FieldEditor'
import { FieldList } from './FieldList'
import { FieldPreview } from './FieldPreview'

function makeKey(existing: FieldDraft[]): string {
  let n = existing.length + 1
  while (existing.some((f) => f.key === `field_${n}`)) n++
  return `field_${n}`
}

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

export function FieldsTab({ eventId }: { eventId: string }) {
  const [fields, setFields] = useState<FieldDraft[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    api.get<FieldDraft[]>(`/api/admin/events/${eventId}/fields`)
      .then((r) => setFields(r.data))
      .catch(() =>
        notifications.show({ color: 'red', title: 'Не удалось загрузить поля', message: '' }),
      )
      .finally(() => setLoading(false))
  }, [eventId])

  function addField() {
    if (!fields) return
    const key = makeKey(fields)
    const next: FieldDraft = {
      key, label: 'Новое поле', field_type: 'text', required: false, order: fields.length,
    }
    const newList = [...fields, next]
    setFields(newList)
    setEditing(newList.length - 1)
  }

  async function save() {
    if (!fields) return
    setSaving(true)
    try {
      const payload = fields.map((f, i) => ({
        order: i,
        key: f.key,
        label: f.label,
        placeholder: f.placeholder ?? null,
        hint: f.hint ?? null,
        field_type: f.field_type,
        required: f.required,
        options: f.options ?? null,
      }))
      const { data } = await api.put<FieldDraft[]>(`/api/admin/events/${eventId}/fields`, payload)
      setFields(data)
      notifications.show({ color: 'teal', title: 'Поля сохранены', message: `${data.length} ${data.length === 1 ? 'поле' : 'поля/полей'}`, autoClose: 2000 })
    } catch (e: any) {
      notifications.show({
        color: 'red',
        title: 'Не удалось сохранить поля',
        message: formatApiError(e?.response?.data?.detail),
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading || !fields) {
    return <Flex justify="center" align="center" py="xl"><Loader /></Flex>
  }

  const hasDuplicateKeys = (() => {
    const seen = new Set<string>()
    for (const f of fields) {
      if (seen.has(f.key)) return true
      seen.add(f.key)
    }
    return false
  })()

  const invalidSelect = fields.filter(
    (f) => (f.field_type === 'select' || f.field_type === 'multi_select') && (!f.options || f.options.length === 0),
  )

  return (
    <Stack gap="lg">
      {hasDuplicateKeys && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
          Есть поля с одинаковым key — каждый ключ должен быть уникальным
        </Alert>
      )}
      {invalidSelect.length > 0 && (
        <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />}>
          Поля «выбор» без вариантов: {invalidSelect.map((f) => f.label || 'без названия').join(', ')}
        </Alert>
      )}

      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="md">
            <Flex justify="space-between" align="center">
              <Stack gap={2}>
                <Title order={5} style={{ color: '#0f172a' }}>Поля анкеты</Title>
                <Text fz="xs" c="dimmed">{fields.length} {fields.length === 1 ? 'поле' : 'полей'} · перетягивайте для сортировки</Text>
              </Stack>
              <Group>
                <Button
                  variant="light"
                  leftSection={<IconPlus size={16} stroke={2} />}
                  onClick={addField}
                >
                  Добавить поле
                </Button>
                <Button
                  leftSection={<IconDeviceFloppy size={16} stroke={2} />}
                  loading={saving}
                  onClick={save}
                  disabled={hasDuplicateKeys}
                  style={{ background: 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)' }}
                >
                  Сохранить поля
                </Button>
              </Group>
            </Flex>

            {fields.length === 0 ? (
              <Paper p="xl" withBorder radius="lg">
                <Stack align="center" gap="xs">
                  <Text c="dimmed" ta="center">У этого мероприятия пока нет полей.</Text>
                  <Text fz="xs" c="dimmed" ta="center">Нажмите «Добавить поле» — конструктор соберёт анкету для бота.</Text>
                </Stack>
              </Paper>
            ) : (
              <FieldList fields={fields} onChange={setFields} onEdit={setEditing} />
            )}
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Paper p="lg" radius="lg" withBorder style={{ position: 'sticky', top: 16 }}>
            <Stack gap="sm">
              <Stack gap={2}>
                <Title order={5} style={{ color: '#0f172a' }}>Превью</Title>
                <Text fz="xs" c="dimmed">Так увидит абитуриент</Text>
              </Stack>
              <FieldPreview fields={fields} />
            </Stack>
          </Paper>
        </Grid.Col>
      </Grid>

      <FieldEditor
        field={editing !== null ? fields[editing] : null}
        opened={editing !== null}
        onClose={() => setEditing(null)}
        onSave={(f) => {
          if (editing === null) return
          setFields(fields.map((x, i) => (i === editing ? f : x)))
        }}
      />
    </Stack>
  )
}
