import { Center, Loader } from '@mantine/core'
import { type ReactNode, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuthStore } from '../stores/auth'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { profile, loadProfile } = useAuthStore()
  const location = useLocation()
  const [checking, setChecking] = useState(profile === null)

  useEffect(() => {
    if (profile !== null) {
      setChecking(false)
      return
    }
    let cancelled = false
    loadProfile()
      .then(() => { if (!cancelled) setChecking(false) })
      .catch(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [profile, loadProfile])

  if (checking) {
    return <Center h="100vh"><Loader /></Center>
  }
  if (profile === null) return <Navigate to="/login" replace />

  // CONTROLLER может находиться только в /controller или на /events/:id/checkin
  // (где LayoutSwitch покажет ControllerLayout). Из остального админ-интерфейса — выкидываем.
  const isControllerCheckin = /^\/events\/[^/]+\/checkin\/?$/.test(location.pathname)
  if (
    profile.role === 'controller'
    && !location.pathname.startsWith('/controller')
    && !isControllerCheckin
  ) {
    return <Navigate to="/controller" replace />
  }
  if (profile.role !== 'controller' && location.pathname.startsWith('/controller')) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
