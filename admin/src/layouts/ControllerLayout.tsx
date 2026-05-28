import { AppShell, Button, Group, Text } from '@mantine/core'
import { Outlet, useNavigate } from 'react-router-dom'

import { api } from '../api'

export function ControllerLayout() {
  const navigate = useNavigate()
  const logout = async () => {
    try {
      await api.post('/api/admin/auth/logout')
    } catch {}
    window.location.href = '/admin/login'
  }
  return (
    <AppShell header={{ height: 56 }} padding={{ base: 'sm', sm: 'md' }}>
      <AppShell.Header>
        <Group h="100%" px={{ base: 'sm', sm: 'md' }} justify="space-between" wrap="nowrap">
          <Text
            fw={700}
            style={{ cursor: 'pointer' }}
            onClick={() => navigate('/controller')}
            truncate
          >
            🎫 Контроль входа
          </Text>
          <Button variant="subtle" size="sm" onClick={() => void logout()}>
            Выйти
          </Button>
        </Group>
      </AppShell.Header>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
