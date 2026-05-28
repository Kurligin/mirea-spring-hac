# Design tokens

Source of truth: `tokens.ts` (TypeScript) + `tokens.css` (CSS variables).

- **admin/** импортирует `tokens.ts` → формирует Mantine theme в `src/theme.ts`
- **mini-app/** импортирует `tokens.css` → использует CSS variables напрямую

При изменении токенов обновляются ОБА файла одновременно.

## Палитра

- **Brand** (синий 50-900) — primary navigation, links, active states
- **Accent** (оранжевый 400-600) — CTA кнопки, важные акценты, бренд РТУ МИРЭА
- **Neutral** (slate 0-900) — текст, фон, бордеры
- **Status** — success/warning/error/info

## Типографика

`Inter` для body и headings, `JetBrains Mono` для кода.

## Шкала

- Spacing: 4px (1) → 96px (24)
- Radius: sm (4px) → 2xl (24px) → full
- Shadow: sm → xl + inner
