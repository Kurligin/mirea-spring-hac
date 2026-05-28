import axios, { AxiosError } from 'axios'

export const api = axios.create({
  baseURL: '/',
  withCredentials: true,
  timeout: 15000,
})

api.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !window.location.pathname.includes('/login')) {
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  },
)

export type AdminRole = 'super' | 'event_manager' | 'viewer' | 'controller'

export interface AdminProfile {
  id: string
  email: string
  role: AdminRole
  full_name: string | null
}

export async function login(email: string, password: string): Promise<AdminProfile> {
  const { data } = await api.post<AdminProfile>('/api/admin/auth/login', { email, password })
  return data
}

export async function loginWithPin(email: string, pin: string): Promise<AdminProfile> {
  const { data } = await api.post<AdminProfile>('/api/admin/auth/login-pin', { email, pin })
  return data
}

export async function getMe(): Promise<AdminProfile> {
  const { data } = await api.get<AdminProfile>('/api/admin/auth/me')
  return data
}

// ── Рекламные рассылки (всем пользователям бота) ──────────────────────
export type AdCampaignStatus = 'draft' | 'scheduled' | 'sending' | 'sent'

export interface AdCampaign {
  id: string
  title: string
  body: string | null
  image_path: string | null
  status: AdCampaignStatus
  send_at: string | null
  sent_at: string | null
  recipients_total: number
  delivered: number
  errors: number
  created_at: string
}

export interface AdCampaignCreate {
  title: string
  body?: string | null
  image_path?: string | null
  send_now?: boolean
  send_at?: string | null
}

export async function uploadBroadcastImage(file: File): Promise<{ path: string; url: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<{ path: string; url: string }>(
    '/api/admin/uploads?kind=broadcast_image',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return data
}

export async function listAdCampaigns(): Promise<AdCampaign[]> {
  const { data } = await api.get<AdCampaign[]>('/api/admin/ad-broadcasts')
  return data
}

export async function createAdCampaign(payload: AdCampaignCreate): Promise<AdCampaign> {
  const { data } = await api.post<AdCampaign>('/api/admin/ad-broadcasts', payload)
  return data
}
