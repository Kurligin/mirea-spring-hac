import { Text } from '@mantine/core'
import { modals } from '@mantine/modals'
import { useEffect, useRef } from 'react'

import { useAuthStore } from '../stores/auth'

const IDLE_LIMIT_MS = 30 * 60_000      // 30 минут абсолютной idle
const WARNING_MS = 60_000              // за минуту до logout — предупреждение

/**
 * Слушает активность пользователя; при бездействии 30 минут — logout
 * с подтверждением «Остаться» / «Выйти». При активности — счётчик сбрасывается.
 */
export function useIdleLogout() {
  const signOut = useAuthStore((s) => s.signOut)
  const profile = useAuthStore((s) => s.profile)
  const warnTimer = useRef<number | null>(null)
  const logoutTimer = useRef<number | null>(null)
  const modalOpen = useRef(false)

  useEffect(() => {
    if (!profile) return

    function clearAll() {
      if (warnTimer.current) { window.clearTimeout(warnTimer.current); warnTimer.current = null }
      if (logoutTimer.current) { window.clearTimeout(logoutTimer.current); logoutTimer.current = null }
    }

    function schedule() {
      clearAll()
      warnTimer.current = window.setTimeout(() => {
        if (modalOpen.current) return
        modalOpen.current = true
        modals.openConfirmModal({
          title: 'Долгое бездействие',
          children: (
            <Text fz="sm">
              Вы давно не делали действий. Через минуту сессия будет закрыта.
            </Text>
          ),
          labels: { confirm: 'Остаться', cancel: 'Выйти' },
          onConfirm: () => { modalOpen.current = false; schedule() },
          onCancel: () => { modalOpen.current = false; signOut() },
          onClose: () => { modalOpen.current = false },
        })
        logoutTimer.current = window.setTimeout(() => {
          if (modalOpen.current) {
            modals.closeAll()
            modalOpen.current = false
          }
          signOut()
        }, WARNING_MS)
      }, IDLE_LIMIT_MS - WARNING_MS)
    }

    function onActivity() {
      if (modalOpen.current) return
      schedule()
    }

    const events: Array<keyof DocumentEventMap> = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart']
    events.forEach((e) => document.addEventListener(e, onActivity, { passive: true }))
    schedule()
    return () => {
      events.forEach((e) => document.removeEventListener(e, onActivity))
      clearAll()
    }
  }, [profile, signOut])
}
