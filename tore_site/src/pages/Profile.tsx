import { FormEvent, useMemo, useState } from 'react';

type AccountMode = 'user' | 'organizer' | 'team';

type MePayload = {
  id: string;
  display_name: string;
  bio?: string | null;
  account_mode?: AccountMode;
  role_request_pending?: { requested_mode: AccountMode; status: string } | null;
};

const API_URL = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '').toString().replace(/\/+$/, '');
const TOKEN_KEY = 'tore_site_token';

export default function ProfilePage() {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '');
  const [me, setMe] = useState<MePayload | null>(null);
  const [msg, setMsg] = useState<string>('');
  const [upgradeCode, setUpgradeCode] = useState('');

  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  async function requestOtp(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API_URL}/auth/email/request_otp`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
    setMsg(res.ok ? 'Code envoyé.' : 'Échec envoi OTP');
  }

  async function verifyOtp(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API_URL}/auth/email/verify_otp`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, code }) });
    const data = await res.json();
    if (!res.ok) return setMsg('OTP invalide');
    const access = (data.access_token || data.accessToken || '').toString();
    localStorage.setItem(TOKEN_KEY, access);
    setToken(access);
    setMsg('Connecté.');
  }

  async function refreshMe() {
    const res = await fetch(`${API_URL}/auth/me`, { headers: authHeaders });
    const data = await res.json();
    if (!res.ok) return setMsg('Erreur /auth/me');
    setMe(data);
  }

  async function saveProfile() {
    if (!me) return;
    const res = await fetch(`${API_URL}/auth/me`, { method: 'PATCH', headers: authHeaders, body: JSON.stringify({ display_name: me.display_name, bio: me.bio || '' }) });
    setMsg(res.ok ? 'Profil enregistré' : 'Erreur profil');
    await refreshMe();
  }

  async function setMode(mode: AccountMode) {
    if (mode === 'user') {
      const res = await fetch(`${API_URL}/auth/me`, { method: 'PATCH', headers: authHeaders, body: JSON.stringify({ account_mode: 'user' }) });
      setMsg(res.ok ? 'Mode utilisateur activé' : 'Erreur mode');
      return refreshMe();
    }
    const res = await fetch(`${API_URL}/auth/role/request-upgrade`, { method: 'POST', headers: authHeaders, body: JSON.stringify({ requested_mode: mode, code: upgradeCode }) });
    setMsg(res.ok ? 'Demande envoyée (en attente).' : 'Code invalide ou erreur.');
    return refreshMe();
  }

  return (
    <main style={{ maxWidth: 760, margin: '32px auto', padding: 16 }}>
      <h1>Profil tore-site</h1>
      <p>Mode actuel: <strong>{me?.account_mode ?? '-'}</strong></p>
      {me?.role_request_pending ? <p>Demande en attente: {me.role_request_pending.requested_mode}</p> : null}

      <form onSubmit={requestOtp} style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder='email' />
        <button type='submit'>Envoyer OTP</button>
      </form>
      <form onSubmit={verifyOtp} style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input value={code} onChange={(e) => setCode(e.target.value)} placeholder='code OTP' />
        <button type='submit'>Vérifier OTP</button>
      </form>
      <button onClick={refreshMe} style={{ marginTop: 10 }}>Rafraîchir /auth/me</button>

      {me ? (
        <section style={{ marginTop: 24 }}>
          <h2>Pseudo/Bio</h2>
          <input value={me.display_name || ''} onChange={(e) => setMe({ ...me, display_name: e.target.value })} placeholder='Pseudo' />
          <textarea value={me.bio || ''} onChange={(e) => setMe({ ...me, bio: e.target.value })} placeholder='Bio' />
          <button onClick={saveProfile}>Sauvegarder</button>

          <h2>Choisir ton mode</h2>
          <input value={upgradeCode} onChange={(e) => setUpgradeCode(e.target.value)} placeholder='Code organizer/team' />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setMode('user')}>Utilisateur</button>
            <button onClick={() => setMode('organizer')}>Organisateur</button>
            <button onClick={() => setMode('team')}>Équipe</button>
          </div>
        </section>
      ) : null}
      {msg ? <p>{msg}</p> : null}
    </main>
  );
}
