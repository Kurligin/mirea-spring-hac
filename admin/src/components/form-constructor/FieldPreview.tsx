import { Box, Code, Flex, Stack, Text } from '@mantine/core'

import { FieldDraft } from './types'

function BotPreview({ fields }: { fields: FieldDraft[] }) {
  if (fields.length === 0) {
    return <Text c="dimmed" ta="center" py="lg">Пока нет полей — добавьте первое</Text>
  }
  return (
    <Stack gap="md">
      {fields.map((f, i) => (
        <Box key={f.key} style={{ padding: 12, background: 'var(--color-neutral-50)', borderRadius: 12 }}>
          <Text fz="xs" c="dimmed" mb={4}>Шаг {i + 1} · бот спросит:</Text>
          <Text fz="sm" fw={500}>{f.label}{f.required ? '' : ' (опционально)'}</Text>
          {f.hint && <Text fz="xs" c="dimmed" mt={2}>{f.hint}</Text>}
          {f.field_type === 'select' && f.options?.length ? (
            <Flex gap={4} mt={6} wrap="wrap">
              {f.options.map((o) => (
                <Code key={o.value}>{o.label}</Code>
              ))}
            </Flex>
          ) : null}
          {f.field_type === 'phone' && (
            <Text fz="xs" c="dimmed" mt={4}>📲 Кнопка «Поделиться контактом»</Text>
          )}
        </Box>
      ))}
    </Stack>
  )
}

export function FieldPreview({ fields }: { fields: FieldDraft[] }) {
  return (
    <Stack gap="md">
      <Text fz="xs" c="dimmed" tt="uppercase" fw={600}>🤖 Превью в боте</Text>
      <Box style={{ minHeight: 200 }}>
        <BotPreview fields={fields} />
      </Box>
    </Stack>
  )
}
