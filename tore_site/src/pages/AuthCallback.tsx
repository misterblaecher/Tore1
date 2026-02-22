import { FormEvent, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiFetch } from '@/lib/api';
import { setCachedMe, setRefreshToken, setToken } from '@/lib/auth';
import { getMe } from '@/lib/session';

type VerifyOut = {
  access_token?: string;
  accessToken?: string;
  refresh_token?: string;
  refreshToken?: string;
};

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const initialEmail = params.get('email') ?? '';
  const tokenParam = params.get('token') ?? params.get('code') ?? '';
  const from = params.get('from') ?? '/';

  const [email, setEmail] = useState(initialEmail);
  const [token, setOtpToken] = useState(tokenParam);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canAutoSubmit = useMemo(() => Boolean(initialEmail && tokenParam), [initialEmail, tokenParam]);

  async function completeAuth(e?: FormEvent) {
    if (e) e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await apiFetch<VerifyOut>('/auth/email/verify_link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, token }),
      });

      const accessToken = data.access_token ?? data.accessToken;
      if (!accessToken) {
        throw new Error('missing access token');
      }

      setToken(accessToken);
      setRefreshToken(data.refresh_token ?? data.refreshToken);

      const me = await getMe(true);
      setCachedMe(me);

      navigate(from, { replace: true });
    } catch {
      setError('Code/lien invalide ou expiré.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 520, margin: '48px auto', padding: 16 }}>
      <h1>Finaliser la connexion</h1>
      <p>Cette page valide le lien/code reçu par email puis récupère votre session.</p>

      {canAutoSubmit ? (
        <button onClick={() => void completeAuth()} disabled={loading}>
          {loading ? 'Connexion…' : 'Terminer la connexion'}
        </button>
      ) : null}

      <form onSubmit={completeAuth} style={{ display: 'grid', gap: 10, marginTop: 12 }}>
        <input
          type="email"
          required
          placeholder="email@exemple.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          required
          placeholder="Code OTP (6 chiffres)"
          value={token}
          onChange={(e) => setOtpToken(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Vérification…' : 'Vérifier'}
        </button>
      </form>

      {error ? <p style={{ color: '#c62828' }}>{error}</p> : null}
    </main>
  );
}
