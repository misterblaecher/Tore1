import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

export function useStructureResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setData(null); setError(null); setLoading(true);
    void apiFetch<T>(path, { signal: controller.signal })
      .then(value => { if (active) setData(value); })
      .catch(reason => { if (active) setError(reason); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [path, revision]);
  return { data, error, loading, reload };
}

export function useStructureWrite() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const locked = useRef(false);
  const pending = useRef<{ fingerprint: string; key: string } | null>(null);
  async function write<T>(path: string, method: string, body?: unknown): Promise<T | undefined> {
    if (locked.current) return undefined;
    locked.current = true; setBusy(true); setError(null);
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const fingerprint = JSON.stringify([path, method, payload]);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
    try {
      const result = await apiFetch<T>(path, { method, body: payload, headers: { "Idempotency-Key": pending.current.key } });
      pending.current = null;
      return result;
    } catch (reason) {
      setError(reason);
      return undefined;
    } finally { locked.current = false; setBusy(false); }
  }
  return { busy, error, write };
}
