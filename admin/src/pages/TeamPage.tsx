import {
  ActionIcon, Avatar, Badge, Box, Button, Card, Flex, Group, Loader, Menu, Modal,
  Paper, PasswordInput, Select, Stack, Switch, Tabs, Text, TextInput, Title,
} from '@mantine/core'
import { modals } from '@mantine/modals'
import {
  IconCheck, IconCrown, IconDotsVertical, IconPencil, IconPlus, IconShieldCheck, IconTrash, IconUser,
} from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import { toast } from '../lib/toast'

interface WebAdmin {
  id: string
  email: string
  role: string
  full_name: string | null
  is_active: boolean
}

interface Team {
  web_admins: WebAdmin[]
}

const ROLE_OPTIONS = [
  { value: 'super',         label: 'Super admin (всё)' },
  { value: 'event_manager', label: 'Event manager (мероприятия)' },
  { value: 'controller',    label: 'Проверяющий (только чек-ин)' },
  { value: 'viewer',        label: 'Viewer (только чтение)' },
]

const ROLE_LABELS: Record<string, string> = {
  super:         'Super admin',
  event_manager: 'Event manager',
  controller:    'Проверяющий',
  viewer:        'Viewer',
}

function RoleIcon({ role }: { role: string | null }) {
  if (role === 'super')         return <IconCrown size={14} stroke={1.8} />
  if (role === 'event_manager') return <IconShieldCheck size={14} stroke={1.8} />
  if (role === 'controller')    return <IconCheck size={14} stroke={1.8} />
  return <IconUser size={14} stroke={1.8} />
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

export function TeamPage() {
  const [team, setTeam] = useState<Team | null>(null)
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [createRole, setCreateRole] = useState<'controller' | 'admin'>('controller')
  const [editTarget, setEditTarget] = useState<WebAdmin | null>(null)
  const me = useAuthStore((s) => s.profile)

  async function reload() {
    setLoading(true)
    try {
      const { data } = await api.get<Team>('/api/admin/team')
      setTeam({ web_admins: data.web_admins })
    } catch {
      toast.error({ title: 'Не удалось загрузить команду' })
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { reload() }, [])

  if (loading || !team) return <Flex justify="center" align="center" py="xl"><Loader /></Flex>

  const controllers = team.web_admins.filter((a) => a.role === 'controller')
  const admins = team.web_admins.filter((a) => a.role !== 'controller')

  return (
    <Stack gap="lg">
      <Flex justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <Stack gap={4}>
          <Title order={2} style={{ color: '#0f172a' }}>Команда</Title>
          <Text c="dimmed" fz="sm">
            Администраторы веба и проверяющие на чек-ине
          </Text>
        </Stack>
      </Flex>

      <Tabs defaultValue="controllers" variant="default">
        <Tabs.List>
          <Tabs.Tab value="controllers" leftSection={<IconCheck size={16} stroke={1.8} />}>
            Проверяющие ({controllers.length})
          </Tabs.Tab>
          <Tabs.Tab value="admins" leftSection={<IconShieldCheck size={16} stroke={1.8} />}>
            Админы ({admins.length})
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="controllers" pt="lg">
          <Stack gap="md">
            <Flex justify="space-between" align="center">
              <Text fz="sm" c="dimmed">
                Назначаются на конкретные мероприятия в редакторе события → вкладка «Контролёры».
              </Text>
              <Button
                leftSection={<IconPlus size={16} stroke={2} />}
                onClick={() => { setCreateRole('controller'); setCreateOpen(true) }}
                style={{ background: 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)' }}
              >
                Создать проверяющего
              </Button>
            </Flex>
            {controllers.length === 0 ? (
              <EmptyTeamState
                icon={<IconCheck size={28} stroke={1.6} />}
                title="Пока нет проверяющих"
                hint="Создайте аккаунт с email и паролем — выдадите проверяющему перед мероприятием."
              />
            ) : (
              <AdminCardList
                admins={controllers}
                meId={me?.id}
                onEdit={setEditTarget}
                onDeleted={reload}
              />
            )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="admins" pt="lg">
          <Stack gap="md">
            <Flex justify="space-between" align="center">
              <Text fz="sm" c="dimmed">
                Super admin видит и редактирует всё; event manager — только свои мероприятия.
              </Text>
              <Button
                variant="default"
                leftSection={<IconPlus size={16} stroke={2} />}
                onClick={() => { setCreateRole('admin'); setCreateOpen(true) }}
              >
                Создать админа
              </Button>
            </Flex>
            {admins.length === 0 ? (
              <EmptyTeamState
                icon={<IconShieldCheck size={28} stroke={1.6} />}
                title="Нет админов"
                hint="Обычно их создают вручную через CLI, но можно и здесь."
              />
            ) : (
              <AdminCardList
                admins={admins}
                meId={me?.id}
                onEdit={setEditTarget}
                onDeleted={reload}
              />
            )}
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <CreateAdminModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        defaultRole={createRole}
        onCreated={() => { setCreateOpen(false); reload() }}
      />

      <EditAdminModal
        target={editTarget}
        onClose={() => setEditTarget(null)}
        onSaved={() => { setEditTarget(null); reload() }}
      />
    </Stack>
  )
}

interface CardListProps {
  admins: WebAdmin[]
  meId: string | undefined
  onEdit: (a: WebAdmin) => void
  onDeleted: () => void
}

function AdminCardList({ admins, meId, onEdit, onDeleted }: CardListProps) {
  async function doDelete(a: WebAdmin) {
    try {
      await api.delete(`/api/admin/team/${a.id}`)
      toast.success({ title: 'Аккаунт деактивирован', message: a.email })
      onDeleted()
    } catch (e: any) {
      toast.error({
        title: 'Не удалось деактивировать',
        message: formatApiError(e?.response?.data?.detail),
      })
    }
  }

  function confirmDelete(a: WebAdmin) {
    modals.openConfirmModal({
      title: 'Деактивировать аккаунт?',
      children: (
        <Text fz="sm">
          {a.full_name || a.email} больше не сможет входить. Историю действий
          (записи на мероприятия, чек-ины, рассылки) удалять не будем — она
          останется для аудита. Восстановить можно позже из карточки.
        </Text>
      ),
      labels: { confirm: 'Деактивировать', cancel: 'Отмена' },
      confirmProps: { color: 'red' },
      onConfirm: () => void doDelete(a),
    })
  }

  return (
    <Stack gap="md">
      {admins.map((a) => {
        const isMe = meId !== undefined && a.id === meId
        return (
          <Card key={a.id} withBorder padding="md" radius="lg">
            <Flex justify="space-between" align="center" gap="sm">
              <Flex align="center" gap="md" style={{ minWidth: 0, flex: 1 }}>
                <Avatar radius="xl" color={a.role === 'controller' ? 'teal' : 'brand'} size="md">
                  {(a.full_name || a.email)[0].toUpperCase()}
                </Avatar>
                <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
                  <Text fw={600} truncate style={{ color: '#0f172a' }}>
                    {a.full_name || a.email}
                    {isMe && <Text component="span" fz="xs" c="dimmed"> · это вы</Text>}
                  </Text>
                  <Text fz="xs" c="dimmed" truncate>{a.email}</Text>
                </Stack>
              </Flex>
              <Group gap="xs" wrap="nowrap">
                <Badge
                  variant="light"
                  color={a.role === 'super' ? 'orange' : a.role === 'controller' ? 'teal' : 'brand'}
                  leftSection={<RoleIcon role={a.role} />}
                >
                  {ROLE_LABELS[a.role] ?? a.role}
                </Badge>
                {!a.is_active && <Badge variant="light" color="gray">Отключён</Badge>}
                <Menu shadow="md" position="bottom-end" width={200}>
                  <Menu.Target>
                    <ActionIcon variant="subtle" aria-label="Действия">
                      <IconDotsVertical size={18} stroke={1.8} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item
                      leftSection={<IconPencil size={16} stroke={1.8} />}
                      onClick={() => onEdit(a)}
                    >
                      Изменить
                    </Menu.Item>
                    <Menu.Divider />
                    <Menu.Item
                      color="red"
                      disabled={isMe}
                      leftSection={<IconTrash size={16} stroke={1.8} />}
                      onClick={() => confirmDelete(a)}
                    >
                      Деактивировать
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              </Group>
            </Flex>
          </Card>
        )
      })}
    </Stack>
  )
}

function EditAdminModal({
  target, onClose, onSaved,
}: {
  target: WebAdmin | null
  onClose: () => void
  onSaved: () => void
}) {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<string>('event_manager')
  const [isActive, setIsActive] = useState(true)
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!target) return
    setEmail(target.email)
    setFullName(target.full_name ?? '')
    setRole(target.role)
    setIsActive(target.is_active)
    setPassword('')
    setPin('')
  }, [target])

  if (!target) return null
  const t = target

  async function save() {
    if (password && password.length < 8) {
      toast.warn({ title: 'Пароль — от 8 символов' })
      return
    }
    if (pin && !/^\d{4,6}$/.test(pin)) {
      toast.warn({ title: 'Пинкод — 4-6 цифр' })
      return
    }
    setBusy(true)
    const payload: Record<string, unknown> = {}
    if (email !== t.email) payload.email = email
    if (fullName !== (t.full_name ?? '')) payload.full_name = fullName || null
    if (role !== t.role) payload.role = role
    if (isActive !== t.is_active) payload.is_active = isActive
    if (password) payload.password = password
    if (pin) payload.pin_code = pin
    try {
      await api.patch(`/api/admin/team/${t.id}`, payload)
      toast.success({ title: 'Сохранено' })
      onSaved()
    } catch (e: any) {
      toast.error({
        title: 'Не удалось сохранить',
        message: formatApiError(e?.response?.data?.detail),
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      opened
      onClose={onClose}
      title={<Title order={4}>Изменить аккаунт</Title>}
      centered
    >
      <Stack gap="md">
        <TextInput
          label="Email"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
          required
        />
        <TextInput
          label="ФИО"
          value={fullName}
          onChange={(e) => setFullName(e.currentTarget.value)}
        />
        <Select
          label="Роль"
          data={ROLE_OPTIONS}
          value={role}
          onChange={(v) => v && setRole(v)}
        />
        <Switch
          label="Активен"
          checked={isActive}
          onChange={(e) => setIsActive(e.currentTarget.checked)}
        />
        <PasswordInput
          label="Новый пароль (опционально)"
          placeholder="оставьте пустым, чтобы не менять"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        {role === 'controller' && (
          <TextInput
            label="Пинкод (опционально)"
            description="4-6 цифр. Пустое поле — оставить как есть."
            placeholder="оставьте пустым, чтобы не менять"
            inputMode="numeric"
            value={pin}
            onChange={(e) => setPin(e.currentTarget.value.replace(/\D/g, '').slice(0, 6))}
          />
        )}
        <Flex justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button onClick={save} loading={busy}>Сохранить</Button>
        </Flex>
      </Stack>
    </Modal>
  )
}

interface CreateAdminModalProps {
  opened: boolean
  onClose: () => void
  defaultRole: 'controller' | 'admin'
  onCreated: () => void
}

function CreateAdminModal({ opened, onClose, defaultRole, onCreated }: CreateAdminModalProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [pin, setPin] = useState('')
  const [role, setRole] = useState<string>('controller')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (opened) {
      setEmail(''); setPassword(''); setFullName(''); setPin('')
      setRole(defaultRole === 'controller' ? 'controller' : 'event_manager')
    }
  }, [opened, defaultRole])

  async function create() {
    if (!email || password.length < 8) {
      toast.warn({ title: 'Заполните email и пароль (от 8 символов)' })
      return
    }
    if (defaultRole === 'controller' && pin && !/^\d{4,6}$/.test(pin)) {
      toast.warn({ title: 'Пинкод — 4-6 цифр' })
      return
    }
    setBusy(true)
    try {
      await api.post('/api/admin/team', {
        email, password, role,
        full_name: fullName || null,
        pin_code: pin || null,
      })
      toast.success({
        title: role === 'controller' ? 'Проверяющий создан' : 'Админ создан',
        message: email,
      })
      onCreated()
    } catch (e: any) {
      toast.error({
        title: 'Не удалось создать аккаунт',
        message: formatApiError(e?.response?.data?.detail),
      })
    } finally {
      setBusy(false)
    }
  }

  const allowedRoles =
    defaultRole === 'controller'
      ? ROLE_OPTIONS.filter((r) => r.value === 'controller')
      : ROLE_OPTIONS.filter((r) => r.value !== 'controller')

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Title order={4}>
          {defaultRole === 'controller' ? 'Новый проверяющий' : 'Новый администратор'}
        </Title>
      }
      centered
    >
      <Stack gap="md">
        <TextInput
          label="Email"
          placeholder="checker@mirea.ru"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
          required
        />
        <PasswordInput
          label="Пароль"
          placeholder="минимум 8 символов"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          required
        />
        <TextInput
          label="ФИО"
          placeholder="Иванов И. И."
          value={fullName}
          onChange={(e) => setFullName(e.currentTarget.value)}
        />
        {defaultRole === 'controller' && (
          <TextInput
            label="Пинкод (опционально)"
            description="4-6 цифр. С пинкодом проверяющий сможет войти быстро на мобиле."
            placeholder="1234"
            value={pin}
            inputMode="numeric"
            onChange={(e) => setPin(e.currentTarget.value.replace(/\D/g, '').slice(0, 6))}
          />
        )}
        {defaultRole !== 'controller' && (
          <Select
            label="Роль"
            data={allowedRoles}
            value={role}
            onChange={(v) => v && setRole(v)}
          />
        )}
        <Flex justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button onClick={create} loading={busy}>Создать</Button>
        </Flex>
      </Stack>
    </Modal>
  )
}

function EmptyTeamState({ icon, title, hint }: { icon: React.ReactNode; title: string; hint: string }) {
  return (
    <Paper withBorder p="xl" radius="lg">
      <Stack align="center" gap="sm">
        <Box
          style={{
            width: 56, height: 56, borderRadius: 14, background: 'rgba(44,84,238,0.08)',
            color: '#2c54ee', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
        <Title order={5} c="dimmed">{title}</Title>
        <Text fz="sm" c="dimmed" ta="center" style={{ maxWidth: 400 }}>{hint}</Text>
      </Stack>
    </Paper>
  )
}

