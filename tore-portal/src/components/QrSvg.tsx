import React, { useMemo } from 'react'
import { generateQrSvg } from '../lib/qr'

export default function QrSvg({ value, size = 220, className }: { value?: string; size?: number; className?: string }) {
  const svg = useMemo(() => (value ? generateQrSvg(value, size) : null), [size, value])
  if (!svg) return null
  return <div className={className} dangerouslySetInnerHTML={{ __html: svg }} />
}
