// Author: 晨星
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'ghost' | 'outline'
type Size = 'sm' | 'md'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  children?: ReactNode
}

const variantClass: Record<Variant, string> = {
  primary: 'bg-accent text-bg hover:brightness-110',
  ghost: 'text-fg-2 hover:bg-surface-2 hover:text-fg',
  outline: 'border border-border-strong text-fg hover:bg-surface-2',
}

const sizeClass: Record<Size, string> = {
  sm: 'h-8 px-2.5 text-[13px]',
  md: 'h-9 px-3.5 text-sm',
}

export function Button({ variant = 'ghost', size = 'md', className = '', children, ...rest }: Props) {
  return (
    <button
      {...rest}
      className={[
        'inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-medium',
        'transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50',
        variantClass[variant],
        sizeClass[size],
        className,
      ].join(' ')}
    >
      {children}
    </button>
  )
}
