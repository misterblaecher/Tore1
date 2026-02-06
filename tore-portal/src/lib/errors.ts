export function isApiUnavailable(error: unknown): boolean {
  if (!error) return false
  if (error instanceof Error) {
    const msg = error.message.toLowerCase()
    return (
      msg.includes('api indisponible') ||
      msg.includes('failed to fetch') ||
      msg.includes('networkerror') ||
      msg.includes('err_network') ||
      msg.includes('load failed')
    )
  }
  return false
}
