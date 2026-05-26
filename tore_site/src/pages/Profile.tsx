import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '@/lib/api';
import { MeResponse, clearToken, setCachedMe } from '@/lib/auth';
import { getMe } from '@/lib/session';

type AccountMode = 'user' | 'organizer' | 'team';

const shell = {
  minHeight: '100vh',
  background: 'radial-gradient(circle at top, rgba(186, 23, 51, 0.18), transparent 34%), #050506',
  color: '#fff',
  padding: '88px 24px 32px',
};

const card = {
  background: '#121217',
  border: '1px solid #2A2631',
  borderRadius: 8,
  padding: 18,
};

const field = {
  width: '100%',
  background: '#050506',
  color: '#fff',
  border: '1px solid #2A2631',
  borderRadius: 8,
  padding: '11px 12px',
  boxSizing: 'border-box' as const,
};

const primaryButton = {
  background: '#BA1733',
  color: '#fff',
  border: 0,
  borderRadius: 8,
  padding: '12px 14px',
  fontWeight: 900,
  cursor: 'pointer',
};

const secondaryButton = {
  background: '#050506',
  color: '#fff',
  border: '1px solid #2A2631',
  borderRadius: 8,
  padding: '12px 14px',
  fontWeight: 700,
  cursor: 'pointer',
};

export default function ProfilePage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [msg, setMsg] = useState('');
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
    setMsg('Profil enregistré.');
  }

  async function setMode(mode: AccountMode) {
    if (mode === 'user') {
      await apiFetch('/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_mode: 'user' }),
      });
      setMsg('Mode utilisateur activé.');
      await refreshMe();
      return;
    }

    await apiFetch('/auth/role/request-upgrade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requested_mode: mode, code: upgradeCode }),
    });
    setMsg('Demande envoyée, en attente de validation.');
    await refreshMe();
  }

  function logout() {
    clearToken();
    setMe(null);
    setMsg('Déconnecté.');
  }

  return (
    <main style={shell}>
      <section style={{ maxWidth: 1040, margin: '0 auto', display: 'grid', gap: 18 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <p style={{ color: '#F4C430', margin: 0, fontWeight: 900 }}>Profil TORÈ</p>
            <h1 style={{ margin: '6px 0', fontSize: 40 }}>Ton compte et tes accès</h1>
            <p style={{ color: '#bbb', maxWidth: 700 }}>
              Modifie ton profil, gère ton mode et ouvre le Studio Comité pour piloter tes soirées.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={refreshMe} style={secondaryButton}>Rafraîchir</button>
            <button onClick={logout} style={secondaryButton}>Se déconnecter</button>
            <Link to="/studio" style={{ ...primaryButton, textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>
              Ouvrir le Studio Comité
            </Link>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 10 }}>
          <div style={card}>
            <strong style={{ fontSize: 13, color: '#bbb' }}>Mode actuel</strong>
            <div style={{ fontSize: 28, fontWeight: 900, marginTop: 8 }}>{me?.account_mode ?? '-'}</div>
          </div>
          <div style={card}>
            <strong style={{ fontSize: 13, color: '#bbb' }}>Email</strong>
            <div style={{ fontSize: 18, fontWeight: 800, marginTop: 8 }}>{me?.email || 'Non renseigné'}</div>
          </div>
          <div style={card}>
            <strong style={{ fontSize: 13, color: '#bbb' }}>Demande en attente</strong>
            <div style={{ fontSize: 18, fontWeight: 800, marginTop: 8 }}>
              {me?.role_request_pending?.requested_mode || 'Aucune'}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.15fr .95fr', gap: 14 }}>
          <section style={card}>
            <h2 style={{ marginTop: 0 }}>Pseudo et bio</h2>
            <div style={{ display: 'grid', gap: 10 }}>
              <input
                style={field}
                value={me?.display_name || ''}
                onChange={(e) => me && setMe({ ...me, display_name: e.target.value })}
                placeholder="Pseudo"
              />
              <textarea
                style={{ ...field, minHeight: 120 }}
                value={me?.bio || ''}
                onChange={(e) => me && setMe({ ...me, bio: e.target.value })}
                placeholder="Bio"
              />
              <button onClick={saveProfile} style={primaryButton}>Sauvegarder</button>
            </div>
          </section>

          <section style={card}>
            <h2 style={{ marginTop: 0 }}>Choisir ton mode</h2>
            <p style={{ color: '#bbb' }}>
              Passe en mode organisateur ou équipe pour débloquer le Studio Comité et la régie TORÈ.
            </p>
            <div style={{ display: 'grid', gap: 10 }}>
              <input
                style={field}
                value={upgradeCode}
                onChange={(e) => setUpgradeCode(e.target.value)}
                placeholder="Code organizer/team"
              />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
                <button onClick={() => void setMode('user')} style={secondaryButton}>Utilisateur</button>
                <button onClick={() => void setMode('organizer')} style={secondaryButton}>Organisateur</button>
                <button onClick={() => void setMode('team')} style={secondaryButton}>Équipe</button>
              </div>
            </div>
          </section>
        </div>

        {msg ? (
          <div style={{ ...card, borderColor: '#F4C430', color: '#F4C430' }}>{msg}</div>
        ) : null}
      </section>
    </main>
  );
}
