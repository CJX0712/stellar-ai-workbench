// Author: 晨星
import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'

const base = [
  'w-full rounded-md bg-surface-2 px-3 text-sm text-fg',
  'placeholder:text-muted border border-border',
  'transition-colors duration-150',
  'focus:border-border-strong focus:outline-none',
].join(' ')

export function Input({ className = '', ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={[base, 'h-9', className].join(' ')} />
}

export function Textarea({ className = '', ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...rest} className={[base, 'min-h-20 resize-y py-2 leading-relaxed', className].join(' ')} />
}
