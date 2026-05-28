import { notifications } from '@mantine/notifications'

interface ToastOptions {
  title?: string
  message?: string
  autoClose?: number | false
}

function show(color: string, defaultTitle: string, opts: ToastOptions | string) {
  const params = typeof opts === 'string' ? { title: opts } : opts
  notifications.show({
    color,
    title: params.title ?? defaultTitle,
    message: params.message ?? '',
    autoClose: params.autoClose ?? 4000,
    withBorder: true,
    radius: 'md',
  })
}

export const toast = {
  success: (opts: ToastOptions | string) => show('teal', 'Готово', opts),
  error: (opts: ToastOptions | string) => show('red', 'Ошибка', opts),
  warn: (opts: ToastOptions | string) => show('orange', 'Внимание', opts),
  info: (opts: ToastOptions | string) => show('blue', '', opts),
}
