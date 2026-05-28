import { create } from 'zustand'

import { AdminProfile, getMe, login as apiLogin, loginWithPin as apiLoginPin } from '../api'

interface AuthState {
  profile: AdminProfile | null
  loading: boolean
  error: string | null
  signIn: (email: string, password: string) => Promise<void>
  signInPin: (email: string, pin: string) => Promise<void>
  loadProfile: () => Promise<void>
  signOut: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  profile: null,
  loading: false,
  error: null,
  async loadProfile() {
    const profile = await getMe()
    set({ profile })
  },
  async signIn(email, password) {
    set({ loading: true, error: null })
    try {
      const profile = await apiLogin(email, password)
      set({ profile, loading: false })
    } catch (e: any) {
      set({ error: e?.response?.data?.detail || 'Ошибка входа', loading: false })
      throw e
    }
  },
  async signInPin(email, pin) {
    set({ loading: true, error: null })
    try {
      const profile = await apiLoginPin(email, pin)
      set({ profile, loading: false })
    } catch (e: any) {
      set({ error: e?.response?.data?.detail || 'Ошибка входа', loading: false })
      throw e
    }
  },
  signOut() {
    set({ profile: null })
    document.cookie = 'admin_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    window.location.href = '/admin/login'
  },
}))
