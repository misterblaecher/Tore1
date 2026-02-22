import { FormEvent, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { API_BASE, apiFetch } from '@/lib/api';

type RequestLinkOut = {
  ok?: boolean;
  code?: string;
};

export default function LoginPage() {
  const location = useLocation();
  const from = (location.state as { from?: string } | undefined)?.from || '/';
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);
  const callbackUrl = useMemo(() => `${window.location.origin}/auth/callback`, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);

    try {
      const out = await apiFetch<RequestLinkOut>('/auth/email/request_link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, redirect_url: callbackUrl }),
      });

      setDevCode(out.code ?? null);
      setMessage('Lien/code envoyé. Ouvre ton email puis termine la connexion.');
    } catch {
      setError('Impossible d’envoyer le lien pour le moment.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 520, margin: '48px auto', padding: 16 }}>
      <h1>Connexion Tore Site</h1>
      <p>Entrez votre email pour recevoir le lien/code de connexion.</p>

      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 10 }}>
        <input
          type="email"
          required
          placeholder="email@exemple.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Envoi…' : 'Envoyer lien'}
        </button>
      </form>

      {message ? <p>{message}</p> : null}
      {error ? <p style={{ color: '#c62828' }}>{error}</p> : null}

      {devCode ? (
        <p>
          DEV code: <code>{devCode}</code> ·{' '}
          <Link to={`/auth/callback?email=${encodeURIComponent(email)}&token=${encodeURIComponent(devCode)}&from=${encodeURIComponent(from)}`}>
            Valider maintenant
          </Link>
        </p>
      ) : null}

      <p>
        Si votre email contient seulement un code OTP, ouvrez{' '}
        <Link to={`/auth/callback?from=${encodeURIComponent(from)}`}>la page callback</Link> pour le saisir.
      </p>
      <small>API: {API_BASE}</small>
    </main>
  );
}
