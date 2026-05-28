import { useEffect, useState } from 'react'
import {
  Alert,
  Anchor,
  Box,
  Button,
  Center,
  Container,
  Flex,
  Paper,
  PasswordInput,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '../stores/auth'

// ─── SVG decorative elements ────────────────────────────────────────────────

function GridPattern() {
  return (
    <svg
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        opacity: 0.12,
        pointerEvents: 'none',
      }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.8" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)" />
    </svg>
  )
}

function CircleOrb({
  cx, cy, r, opacity,
}: { cx: string; cy: string; r: number; opacity: number }) {
  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill="white"
      opacity={opacity}
      style={{ filter: 'blur(60px)' }}
    />
  )
}

function BrandIllustration() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 500 340"
      xmlns="http://www.w3.org/2000/svg"
      style={{ width: '100%', maxWidth: 420, opacity: 0.22 }}
    >
      <polygon points="170,30 230,65 230,135 170,170 110,135 110,65" fill="none" stroke="white" strokeWidth="1.5" />
      <polygon points="230,65 290,30 350,65 350,135 290,170 230,135" fill="none" stroke="white" strokeWidth="1.5" />
      <polygon points="170,170 230,135 230,205 170,240 110,205 110,135" fill="none" stroke="white" strokeWidth="1.5" />
      <polygon points="230,135 290,170 290,240 230,275 170,240 170,170" fill="none" stroke="white" strokeWidth="1.5" />
      <polygon points="290,170 350,135 410,170 410,240 350,275 290,240" fill="none" stroke="white" strokeWidth="1.5" />
      {[
        [170, 30], [230, 65], [290, 30], [350, 65], [110, 65], [410, 170],
        [170, 170], [230, 205], [290, 170], [350, 135], [110, 135],
        [170, 240], [230, 275], [290, 240], [350, 275], [410, 240],
      ].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={3} fill="white" opacity={0.8} />
      ))}
    </svg>
  )
}

function LogoMark() {
  return (
    <svg
      width="48"
      height="48"
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ flexShrink: 0 }}
    >
      <rect width="48" height="48" rx="12" fill="rgba(255,255,255,0.2)" />
      <path
        d="M10 36V14l14 14 14-14v22"
        stroke="white"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  )
}

const injectStyles = (() => {
  let done = false
  return () => {
    if (done) return
    done = true
    const s = document.createElement('style')
    s.textContent = `
      @keyframes fadeSlide { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }
      .login-field input:focus, .login-field input:focus-visible {
        outline: 2px solid #2c54ee !important;
        border-color: #2c54ee !important;
      }
      .login-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(44,84,238,0.38) !important; }
      .login-btn { transition: transform 0.18s ease, box-shadow 0.18s ease; }
    `
    document.head.appendChild(s)
  }
})()

export function LoginPage() {
  const navigate = useNavigate()
  const { signIn, signInPin, loading, error } = useAuthStore()
  const [mounted, setMounted] = useState(false)
  const [mode, setMode] = useState<'password' | 'pin'>('password')

  useEffect(() => {
    injectStyles()
    setMounted(true)
  }, [])

  const form = useForm({
    initialValues: { email: '', password: '', pin: '' },
    validate: {
      email: (v) => (/^\S+@\S+$/.test(v) ? null : 'Невалидный email'),
      password: (v) =>
        mode === 'password'
          ? v.length >= 4 ? null : 'Минимум 4 символа'
          : null,
      pin: (v) =>
        mode === 'pin'
          ? /^\d{4,6}$/.test(v) ? null : '4-6 цифр'
          : null,
    },
  })

  async function onSubmit(values: typeof form.values) {
    try {
      if (mode === 'pin') {
        await signInPin(values.email, values.pin)
      } else {
        await signIn(values.email, values.password)
      }
      navigate('/')
    } catch {
      /* error handled in store */
    }
  }

  return (
    <Flex h="100vh" w="100vw" style={{ overflow: 'hidden' }}>

      {/* ── LEFT: Brand panel ─── скрыта на мобиле, чтобы форма заняла весь экран */}
      <Box
        flex={1}
        visibleFrom="md"
        style={{
          position: 'relative',
          background:
            'linear-gradient(145deg, #162f9c 0%, #2c54ee 42%, #cc430a 78%, #ff6b1f 100%)',
          color: '#fff',
          padding: '3rem 3.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          overflow: 'hidden',
          minWidth: 0,
        }}
      >
        <GridPattern />

        <svg
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
          }}
        >
          <CircleOrb cx="80%"  cy="15%"  r={160} opacity={0.13} />
          <CircleOrb cx="10%"  cy="75%"  r={200} opacity={0.10} />
          <CircleOrb cx="55%"  cy="50%"  r={90}  opacity={0.07} />
        </svg>

        <Flex align="center" gap="sm" style={{ position: 'relative', zIndex: 1 }}>
          <LogoMark />
          <Stack gap={0}>
            <Text fw={700} fz="lg" lh={1.2}>МАКС-2</Text>
            <Text fz="xs" opacity={0.75} lh={1.2}>РТУ МИРЭА</Text>
          </Stack>
        </Flex>

        <Stack
          gap="lg"
          style={{
            position: 'relative',
            zIndex: 1,
            animation: mounted ? 'fadeSlide 0.6s ease both' : undefined,
          }}
        >
          <BrandIllustration />
          <Stack gap="xs">
            <Title
              order={1}
              c="white"
              style={{ fontSize: 'clamp(2rem, 3.5vw, 3rem)', lineHeight: 1.15 }}
            >
              Запись&nbsp;абитуриентов
            </Title>
            <Text fz="lg" opacity={0.85} style={{ maxWidth: 400, lineHeight: 1.55 }}>
              Гибкий чат-бот и mini-app в мессенджере МАКС — приёмная комиссия теперь в кармане.
            </Text>
          </Stack>

          <Flex gap="xs" wrap="wrap">
            {['Чат-бот', 'Mini-app', 'Аналитика'].map((label) => (
              <Box
                key={label}
                style={{
                  background: 'rgba(255,255,255,0.15)',
                  backdropFilter: 'blur(8px)',
                  border: '1px solid rgba(255,255,255,0.25)',
                  borderRadius: 9999,
                  padding: '4px 14px',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  color: '#fff',
                  letterSpacing: '0.02em',
                }}
              >
                {label}
              </Box>
            ))}
          </Flex>
        </Stack>

        <Text opacity={0.55} fz="xs" style={{ position: 'relative', zIndex: 1 }}>
          Хакатон «Весенний код» 2026
        </Text>
      </Box>

      {/* ── RIGHT: Login form ──────────────────────────────────────────────── */}
      <Center
        flex={1}
        style={{
          position: 'relative',
          background: '#f8fafc',
          minWidth: 0,
        }}
      >
        <Box
          style={{
            position: 'absolute',
            top: -80,
            right: -80,
            width: 280,
            height: 280,
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(44,84,238,0.08) 0%, transparent 70%)',
            pointerEvents: 'none',
          }}
        />

        <Container
          size={420}
          px="xl"
          w="100%"
          style={{ position: 'relative', zIndex: 1 }}
        >
          <Stack
            gap="xl"
            style={{
              animation: mounted ? 'fadeSlide 0.55s 0.1s ease both' : undefined,
            }}
          >
            <Stack gap={6}>
              <Title
                order={2}
                style={{ fontSize: '1.75rem', color: '#0f172a', lineHeight: 1.2 }}
              >
                Вход в панель
              </Title>
              <Text c="dimmed" fz="sm" style={{ lineHeight: 1.55 }}>
                Используйте корпоративную почту и пароль администратора.
              </Text>
            </Stack>

            <Paper
              p="xl"
              radius="xl"
              style={{
                background: 'rgba(255,255,255,0.85)',
                backdropFilter: 'blur(16px)',
                border: '1px solid rgba(226,232,240,0.9)',
                boxShadow:
                  '0 4px 6px -1px rgba(0,0,0,0.06), 0 2px 4px -2px rgba(0,0,0,0.04), 0 0 0 1px rgba(44,84,238,0.04)',
              }}
            >
              <form onSubmit={form.onSubmit(onSubmit)}>
                <Stack gap="md">
                  <SegmentedControl
                    fullWidth
                    value={mode}
                    onChange={(v) => setMode(v as 'password' | 'pin')}
                    data={[
                      { value: 'password', label: 'Пароль' },
                      { value: 'pin', label: 'Пинкод' },
                    ]}
                  />

                  <Box className="login-field">
                    <TextInput
                      label="Email"
                      placeholder="you@mirea.ru"
                      required
                      size="md"
                      styles={{
                        label: { fontWeight: 500, marginBottom: 6, color: '#334155' },
                        input: {
                          borderColor: '#e2e8f0',
                          borderRadius: 8,
                          transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
                        },
                      }}
                      {...form.getInputProps('email')}
                    />
                  </Box>

                  {mode === 'password' ? (
                    <Box className="login-field">
                      <PasswordInput
                        label="Пароль"
                        placeholder="••••••••"
                        required
                        size="md"
                        styles={{
                          label: { fontWeight: 500, marginBottom: 6, color: '#334155' },
                          input: {
                            borderColor: '#e2e8f0',
                            borderRadius: 8,
                            transition: 'border-color 0.15s ease',
                          },
                        }}
                        {...form.getInputProps('password')}
                      />
                    </Box>
                  ) : (
                    <Box className="login-field">
                      <TextInput
                        label="Пинкод"
                        placeholder="4-6 цифр"
                        required
                        size="md"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        styles={{
                          label: { fontWeight: 500, marginBottom: 6, color: '#334155' },
                          input: {
                            borderColor: '#e2e8f0',
                            borderRadius: 8,
                            fontSize: '1.25rem',
                            letterSpacing: '0.3em',
                            textAlign: 'center',
                          },
                        }}
                        value={form.values.pin}
                        onChange={(e) => form.setFieldValue('pin', e.currentTarget.value.replace(/\D/g, '').slice(0, 6))}
                        error={form.errors.pin}
                      />
                    </Box>
                  )}

                  {error && (
                    <Alert
                      color="red"
                      variant="light"
                      radius="md"
                      style={{ fontSize: '0.875rem' }}
                    >
                      {error}
                    </Alert>
                  )}

                  <Button
                    type="submit"
                    loading={loading}
                    fullWidth
                    size="md"
                    className="login-btn"
                    style={{
                      background: 'linear-gradient(135deg, #2c54ee 0%, #1e3fcc 100%)',
                      border: 'none',
                      fontWeight: 600,
                      letterSpacing: '0.02em',
                      borderRadius: 8,
                    }}
                  >
                    Войти
                  </Button>
                </Stack>
              </form>
            </Paper>

            <Text c="dimmed" fz="xs" ta="center" style={{ lineHeight: 1.5 }}>
              Нет аккаунта? Запросите у{' '}
              <Anchor href="mailto:admissions@mirea.ru" fz="xs" c="blue">
                admissions@mirea.ru
              </Anchor>
            </Text>
          </Stack>
        </Container>
      </Center>
    </Flex>
  )
}
