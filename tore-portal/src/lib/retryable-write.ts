/** One user intent keeps its key after an ambiguous failure and across double taps. */
export function createRetryableWrite<T>(send: (body: string, key: string) => Promise<T>) {
  let intent: { body: string; key: string } | null = null
  let pending: Promise<T> | null = null
  return (payload: Record<string, unknown>): Promise<T> => {
    const body = JSON.stringify(payload)
    if (pending) {
      if (intent?.body === body) return pending
      return Promise.reject(new Error('Une opération est déjà en cours'))
    }
    if (!intent || intent.body !== body) intent = { body, key: crypto.randomUUID() }
    const key = intent.key
    pending = Promise.resolve().then(() => send(body, key)).then((result) => {
      intent = null
      return result
    }).finally(() => { pending = null })
    return pending
  }
}
