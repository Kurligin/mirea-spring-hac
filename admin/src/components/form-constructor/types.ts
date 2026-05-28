export type FieldType =
  | 'text'
  | 'textarea'
  | 'email'
  | 'phone'
  | 'number'
  | 'date'
  | 'select'
  | 'multi_select'
  | 'consent'

export interface FieldOption {
  value: string
  label: string
}

export interface FieldDraft {
  id?: string   // server uuid (undefined для новых)
  key: string
  label: string
  placeholder?: string | null
  hint?: string | null
  field_type: FieldType
  required: boolean
  options?: FieldOption[] | null
  order: number
}

export const FIELD_TYPE_META: Record<FieldType, { label: string; icon: string; supportsOptions: boolean }> = {
  text:         { label: 'Короткий текст',        icon: 'IconAbc',           supportsOptions: false },
  textarea:     { label: 'Длинный текст',         icon: 'IconAlignLeft',     supportsOptions: false },
  email:        { label: 'Email',                 icon: 'IconAt',            supportsOptions: false },
  phone:        { label: 'Телефон',               icon: 'IconPhone',         supportsOptions: false },
  number:       { label: 'Число',                 icon: 'IconHash',          supportsOptions: false },
  date:         { label: 'Дата',                  icon: 'IconCalendar',      supportsOptions: false },
  select:       { label: 'Выбор одного',          icon: 'IconCircleDot',     supportsOptions: true  },
  multi_select: { label: 'Выбор нескольких',      icon: 'IconChecks',        supportsOptions: true  },
  consent:      { label: 'Согласие (чекбокс)',    icon: 'IconCheckbox',      supportsOptions: false },
}
