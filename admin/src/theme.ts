import { createTheme, type MantineThemeOverride } from '@mantine/core'

import { colors, radius, shadow, typography } from '@design/tokens'

const brand = Object.values(colors.brand) as unknown as [
  string, string, string, string, string, string, string, string, string, string
]

export const theme: MantineThemeOverride = createTheme({
  primaryColor: 'brand',
  primaryShade: 5,
  colors: {
    brand: brand,
  },
  fontFamily: typography.fontFamily.body,
  headings: { fontFamily: typography.fontFamily.heading, fontWeight: '600' },
  defaultRadius: radius.md,
  shadows: {
    sm: shadow.sm, md: shadow.md, lg: shadow.lg, xl: shadow.xl,
  },
  components: {
    Button: { defaultProps: { radius: 'md' } },
    Card: { defaultProps: { radius: 'lg', withBorder: true } },
    Paper: { defaultProps: { radius: 'lg' } },
  },
})
