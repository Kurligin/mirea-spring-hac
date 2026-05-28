import { Box, ScrollArea, Stack, Text, ThemeIcon } from '@mantine/core'
import {
  IconCalendar,
  IconCalendarEvent,
  IconHistory,
  IconLayoutDashboard,
  IconSpeakerphone,
  IconUsers,
} from '@tabler/icons-react'
import type { ReactNode } from 'react'
import { NavLink as RouterLink, useLocation } from 'react-router-dom'

import { useAuthStore } from '../stores/auth'

interface SidebarItem {
  to: string
  label: string
  icon: ReactNode
  superOnly?: boolean
}

const ITEMS: SidebarItem[] = [
  { to: '/', label: 'Дашборд', icon: <IconLayoutDashboard size={18} stroke={1.8} /> },
  { to: '/events', label: 'Мероприятия', icon: <IconCalendarEvent size={18} stroke={1.8} /> },
  { to: '/calendar', label: 'Календарь', icon: <IconCalendar size={18} stroke={1.8} /> },
  { to: '/ad-broadcasts', label: 'Рассылки', icon: <IconSpeakerphone size={18} stroke={1.8} /> },
  { to: '/team', label: 'Команда', icon: <IconUsers size={18} stroke={1.8} /> },
  { to: '/audit', label: 'Журнал', icon: <IconHistory size={18} stroke={1.8} />, superOnly: true },
]

export function Sidebar() {
  const loc = useLocation()
  const role = useAuthStore((s) => s.profile?.role)
  const items = ITEMS.filter((it) => !it.superOnly || role === 'super')
  return (
    <Stack gap={4} p="md">
      <Text fz="xs" c="dimmed" fw={600} mb="xs" pl="xs">НАВИГАЦИЯ</Text>
      <ScrollArea>
        <Stack gap={2}>
          {items.map((item) => {
            const active =
              item.to === '/'
                ? loc.pathname === '/' || loc.pathname === ''
                : loc.pathname.startsWith(item.to)
            return (
              <RouterLink
                key={item.to}
                to={item.to}
                style={{ textDecoration: 'none', display: 'block' }}
              >
                <Box
                  style={{
                    position: 'relative',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '10px 12px 10px 16px',
                    borderRadius: 10,
                    background: active ? 'rgba(44,84,238,0.10)' : 'transparent',
                    color: active ? '#1e3fcc' : '#334155',
                    fontWeight: active ? 600 : 500,
                    transition: 'background 0.14s ease, color 0.14s ease',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) e.currentTarget.style.background = 'var(--color-neutral-50)'
                  }}
                  onMouseLeave={(e) => {
                    if (!active) e.currentTarget.style.background = 'transparent'
                  }}
                >
                  {active && (
                    <Box
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: 8,
                        bottom: 8,
                        width: 3,
                        borderRadius: 2,
                        background: '#2c54ee',
                      }}
                    />
                  )}
                  <ThemeIcon
                    variant="light"
                    size="md"
                    radius="md"
                    color={active ? 'brand' : 'gray'}
                  >
                    {item.icon}
                  </ThemeIcon>
                  <Text fz="sm" inherit>{item.label}</Text>
                </Box>
              </RouterLink>
            )
          })}
        </Stack>
      </ScrollArea>
    </Stack>
  )
}
