import { expect, test, vi } from 'vitest'
import { createRetryableWrite } from './retryable-write'

test('ambiguous network failure reuses the key; successful next intent gets a fresh key', async () => {
  const send = vi.fn().mockRejectedValueOnce(new Error('connection lost')).mockResolvedValue({ ok: true })
  const write = createRetryableWrite(send)
  const payload = { event_id: 4, target_user_id: 'member', amount_cents: 12 }
  await expect(write(payload)).rejects.toThrow('connection lost')
  await write(payload)
  expect(send.mock.calls[1][1]).toBe(send.mock.calls[0][1])
  await write(payload)
  expect(send.mock.calls[2][1]).not.toBe(send.mock.calls[1][1])
})
test('double tap performs one write and cannot replace the in-flight recipient', async () => {
  let resolve!: (value: boolean) => void
  const send = vi.fn(() => new Promise<boolean>((done) => { resolve = done }))
  const write = createRetryableWrite(send)
  const first = write({ target: 'A', amount: 10 })
  expect(write({ target: 'A', amount: 10 })).toBe(first)
  await expect(write({ target: 'B', amount: 10 })).rejects.toThrow('déjà en cours')
  expect(send).toHaveBeenCalledTimes(1)
  resolve(true)
  await first
})
