import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { MeResponse, clearToken, setCachedMe } from '@/lib/auth';
import { getMe } from '@/lib/session';

type AccountMode = 'user' | 'organizer' | 'team';

export default function ProfilePage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [msg, setMsg] = useState<string>('');
  const [upgradeCode, setUpgradeCode] = useState('');

  useEffect(() => {
    void refreshMe();
  }, []);

  async function refreshMe() {
    try {
      const payload = await getMe(true);
      setMe(payload);
      setMsg('');
    } catch {
      setMsg('Session expirée, reconnectez-vous.');
    }
  }

  async function saveProfile() {
    if (!me) return;
    const updated = await apiFetch<MeResponse>('/auth/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: me.display_name, bio: me.bio || '' }),
    });
    setMe(updated);
    setCachedMe(updated);
    setMsg('Profil enregistré');
  }

  async function setMode(mode: AccountMode) {
    if (mode === 'user') {
      await apiFetch('/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_mode: 'user' }),
      });
      setMsg('Mode utilisateur activé');
      await refreshMe();
      return;
    }

    await apiFetch('/auth/role/request-upgrade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requested_mode: mode, code: upgradeCode }),
    });
    setMsg('Demande envoyée (en attente).');
    await refreshMe();
  }

  function logout() {
    clearToken();
    setMe(null);
    setMsg('Déconnecté.');
  }

  return (
    <main style={{ maxWidth: 760, margin: '32px auto', padding: 16 }}>
      <h1>Profil tore-site</h1>
      <p>Mode actuel: <strong>{me?.account_mode ?? '-'}</strong></p>
      {me?.role_request_pending ? <p>Demande en attente: {me.role_request_pending.requested_mode}</p> : null}

      <button onClick={refreshMe} style={{ marginTop: 10 }}>Rafraîchir /auth/me</button>
      <button onClick={logout} style={{ marginTop: 10, marginLeft: 8 }}>Se déconnecter</button>

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
