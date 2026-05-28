import { Center, Loader } from '@mantine/core'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'

import { ProtectedRoute } from './components/ProtectedRoute'
import { LayoutSwitch } from './components/LayoutSwitch'
import { ControllerHomePage } from './pages/ControllerHomePage'
import { DashboardPage } from './pages/DashboardPage'
import { EventsListPage } from './pages/EventsListPage'
import { LoginPage } from './pages/LoginPage'
import { TeamPage } from './pages/TeamPage'

const AdBroadcastsPage = lazy(() =>
  import('./pages/AdBroadcastsPage').then((m) => ({ default: m.AdBroadcastsPage })),
)
const AuditPage = lazy(() => import('./pages/AuditPage').then((m) => ({ default: m.AuditPage })))
const CalendarPage = lazy(() => import('./pages/CalendarPage').then((m) => ({ default: m.CalendarPage })))
const EventCheckinPage = lazy(() =>
  import('./pages/EventCheckinPage').then((m) => ({ default: m.EventCheckinPage })),
)
const EventEditorPage = lazy(() =>
  import('./pages/EventEditorPage').then((m) => ({ default: m.EventEditorPage })),
)

function PageSuspense({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <Center h="60vh">
          <Loader />
        </Center>
      }
    >
      {children}
    </Suspense>
  )
}

const router = createBrowserRouter(
  [
    { path: '/login', element: <LoginPage /> },
    {
      path: '/',
      element: (
        <ProtectedRoute>
          <LayoutSwitch />
        </ProtectedRoute>
      ),
      children: [
        { index: true, element: <DashboardPage /> },
        { path: 'events', element: <EventsListPage /> },
        { path: 'events/:id', element: <PageSuspense><EventEditorPage /></PageSuspense> },
        { path: 'events/:id/checkin', element: <PageSuspense><EventCheckinPage /></PageSuspense> },
        { path: 'calendar', element: <PageSuspense><CalendarPage /></PageSuspense> },
        { path: 'ad-broadcasts', element: <PageSuspense><AdBroadcastsPage /></PageSuspense> },
        { path: 'audit', element: <PageSuspense><AuditPage /></PageSuspense> },
        { path: 'scanner', element: <Navigate to="/" replace /> },
        { path: 'team', element: <TeamPage /> },
      ],
    },
    {
      path: '/controller',
      element: (
        <ProtectedRoute>
          <LayoutSwitch />
        </ProtectedRoute>
      ),
      children: [{ index: true, element: <ControllerHomePage /> }],
    },
    { path: '*', element: <Navigate to="/" replace /> },
  ],
  { basename: '/admin' },
)

export default function App() {
  return <RouterProvider router={router} />
}
