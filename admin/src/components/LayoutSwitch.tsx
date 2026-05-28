import { useAuthStore } from '../stores/auth'
import { ControllerLayout } from '../layouts/ControllerLayout'
import { useIdleLogout } from '../hooks/useIdleLogout'
import { AdminAppShell } from './AppShell'

export function LayoutSwitch() {
  const profile = useAuthStore((s) => s.profile)
  useIdleLogout()
  if (profile?.role === 'controller') {
    return <ControllerLayout />
  }
  return <AdminAppShell />
}
