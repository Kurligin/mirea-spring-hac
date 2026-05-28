import '@mantine/core/styles.css'
import '@mantine/dates/styles.css'
import '@mantine/notifications/styles.css'
import '@design/tokens.css'

import { MantineProvider } from '@mantine/core'
import { DatesProvider } from '@mantine/dates'
import { ModalsProvider } from '@mantine/modals'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import dayjs from 'dayjs'
import 'dayjs/locale/ru'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { theme } from './theme'

dayjs.locale('ru')

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: 1,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme}>
        <DatesProvider settings={{ locale: 'ru', firstDayOfWeek: 1, weekendDays: [0, 6] }}>
          <ModalsProvider
            labels={{ confirm: 'Подтвердить', cancel: 'Закрыть' }}
            modalProps={{ centered: true, radius: 'lg' }}
          >
            <Notifications position="top-right" zIndex={2000} />
            <App />
          </ModalsProvider>
        </DatesProvider>
      </MantineProvider>
    </QueryClientProvider>
  </StrictMode>,
)
