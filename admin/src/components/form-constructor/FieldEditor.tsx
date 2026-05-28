import {
  ActionIcon, Box, Button, Flex, Modal, Select, Stack, Switch, Text, TextInput, Title,
} from '@mantine/core'
import { IconPlus, IconTrash } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import { FIELD_TYPE_META, FieldDraft, FieldOption, FieldType } from './types'

const TYPE_OPTIONS = (Object.keys(FIELD_TYPE_META) as FieldType[]).map((t) => ({
  value: t, label: FIELD_TYPE_META[t].label,
}))

export function FieldEditor({
  field, opened, onClose, onSave,
}: {
  field: FieldDraft | null
  opened: boolean
  onClose: () => void
  onSave: (f: FieldDraft) => void
}) {
  const [draft, setDraft] = useState<FieldDraft | null>(field)
  useEffect(() => { setDraft(field) }, [field])

  if (!draft) return null

  const supportsOptions = FIELD_TYPE_META[draft.field_type].supportsOptions

  function update<K extends keyof FieldDraft>(k: K, v: FieldDraft[K]) {
    setDraft((d) => (d ? { ...d, [k]: v } : d))
  }

  function addOption() {
    const next: FieldOption = { value: `option_${(draft!.options?.length || 0) + 1}`, label: 'Новый вариант' }
    update('options', [...(draft!.options || []), next])
  }

  function updateOption(idx: number, patch: Partial<FieldOption>) {
    const next = (draft!.options || []).map((o, i) => (i === idx ? { ...o, ...patch } : o))
    update('options', next)
  }

  function removeOption(idx: number) {
    update('options', (draft!.options || []).filter((_, i) => i !== idx))
  }

  function handleSave() {
    if (!draft) return
    if (!draft.key.match(/^[a-z][a-z0-9_]*$/)) return
    if (!draft.label.trim()) return
    onSave(draft)
    onClose()
  }

  return (
    <Modal opened={opened} onClose={onClose} title={<Title order={4}>Поле формы</Title>} size="lg" centered>
      <Stack gap="md">
        <Select
          label="Тип поля"
          description="Как абитуриент будет отвечать"
          data={TYPE_OPTIONS}
          value={draft.field_type}
          onChange={(v) => v && update('field_type', v as FieldType)}
        />
        <TextInput
          label="Подпись"
          description="Вопрос, который увидит абитуриент"
          placeholder="Ваше ФИО"
          required
          value={draft.label}
          onChange={(e) => update('label', e.currentTarget.value)}
        />
        <TextInput
          label="Подсказка"
          description="Появится под полем серым шрифтом (необязательно)"
          placeholder="Как в паспорте"
          value={draft.hint ?? ''}
          onChange={(e) => update('hint', e.currentTarget.value || null)}
        />
        <Switch
          label="Обязательное поле"
          checked={draft.required}
          onChange={(e) => update('required', e.currentTarget.checked)}
        />

        {supportsOptions && (
          <Stack gap="xs">
            <Flex justify="space-between" align="center">
              <Stack gap={2}>
                <Text fw={600} fz="sm">Варианты ответа</Text>
                <Text fz="xs" c="dimmed">Что показать в селекте</Text>
              </Stack>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconPlus size={14} stroke={2} />}
                onClick={addOption}
              >
                Добавить
              </Button>
            </Flex>
            <Stack gap="xs">
              {(draft.options || []).map((o, i) => (
                <Flex key={i} gap="xs" align="center">
                  <TextInput
                    placeholder="value"
                    value={o.value}
                    onChange={(e) => updateOption(i, { value: e.currentTarget.value })}
                    style={{ flex: 1 }}
                  />
                  <TextInput
                    placeholder="Что увидит юзер"
                    value={o.label}
                    onChange={(e) => updateOption(i, { label: e.currentTarget.value })}
                    style={{ flex: 2 }}
                  />
                  <ActionIcon variant="subtle" color="red" onClick={() => removeOption(i)}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Flex>
              ))}
              {(draft.options || []).length === 0 && (
                <Box style={{ padding: 16, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
                  Нет вариантов — добавьте хотя бы один
                </Box>
              )}
            </Stack>
          </Stack>
        )}

        <Flex justify="flex-end" gap="sm" pt="md">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button onClick={handleSave}>Сохранить</Button>
        </Flex>
      </Stack>
    </Modal>
  )
}
