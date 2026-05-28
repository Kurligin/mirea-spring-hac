import { ActionIcon, AppShell as MantineAppShell, Avatar, Box, Group, Menu, Text } from '@mantine/core'
import { Outlet } from 'react-router-dom'

import { useAuthStore } from '../stores/auth'
import { Sidebar } from './Sidebar'

export function AdminAppShell() {
  const { profile, signOut } = useAuthStore()
  return (
    <MantineAppShell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: 'sm' }}
      padding="md"
    >
      <MantineAppShell.Header>
        <Group justify="space-between" h="100%" px="md">
          <Group>
            <Box
              style={{
                width: 32, height: 32, borderRadius: 'var(--radius-md)',
                background:
                  'linear-gradient(135deg, var(--color-brand-500), var(--color-accent-500))',
              }}
            />
            <Text fw={600}>МАКС-2 · Админ</Text>
          </Group>
          <Menu shadow="md" position="bottom-end">
            <Menu.Target>
              <ActionIcon variant="subtle" size="lg" radius="xl">
                <Avatar radius="xl" size="sm" color="brand">
                  {(profile?.email || 'A')[0].toUpperCase()}
                </Avatar>
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>{profile?.email || 'admin'}</Menu.Label>
              <Menu.Item onClick={signOut}>Выйти</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </MantineAppShell.Header>
      <MantineAppShell.Navbar><Sidebar /></MantineAppShell.Navbar>
      <MantineAppShell.Main><Outlet /></MantineAppShell.Main>
    </MantineAppShell>
  )
}
