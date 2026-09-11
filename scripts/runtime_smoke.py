"""Small, repeatable smoke against a REAL local server, never a production target.

Run with tore-backend/.venv-release/Scripts/python.exe scripts/runtime_smoke.py.
Seeds the dedicated runtime-smoke SQLite database only. Credentials stay in data/.
"""
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
os.environ['DATABASE_URL'] = 'sqlite:///' + (ROOT / 'tore-backend/data/runtime-smoke.db').as_posix()
os.environ['TORE_ENV'] = 'dev'
sys.path.insert(0, str(ROOT / 'tore-backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
BASE = 'http://127.0.0.1:8001'
client = httpx.Client(base_url=BASE, timeout=20)
checks = []

def request(method, path, token=None, expected=200, key=None, **kwargs):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if key:
        headers['Idempotency-Key'] = key
    response = client.request(method, path, headers=headers, **kwargs)
    assert response.status_code == expected, f'{method} {path}: {response.status_code}, expected {expected}: {response.text[:350]}'
    checks.append(f'{method} {path} => {expected}')
    return response.json() if response.content else None

def account(name):
    email = f'{name}@smoke.tore.test'
    body = dict(email=email, password='ToreLocalSmoke-2026!')
    response = client.post('/auth/password/register', json={**body, 'first_name': name, 'last_name': 'Local', 'nickname': name})
    assert response.status_code in (200, 409), response.text
    data = request('POST', '/auth/password/login', json=body)
    return data['access_token']

def main():
    assert request('GET', '/healthz')['db_ok']
    import seed_minimal
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        seed_minimal.main()
    seed = json.loads(output.getvalue())
    tokens = {name: account(name) for name in ['smoke-owner-a', 'smoke-owner-b', 'smoke-member']}
    structures = {}
    for suffix in ['a', 'b']:
        token = tokens[f'smoke-owner-{suffix}']
        data = request('POST', '/orgas', token, key=f'runtime-structure-{suffix}', json={
            'name': f'TORÈ Smoke {suffix.upper()} — local', 'city': 'Liège', 'org_type': 'COMMITTEE',
            'description': 'Structure de test locale. Aucune donnée de production.',
        })
        structures[suffix] = data['orga']
    a, b = structures['a'], structures['b']
    owner = tokens['smoke-owner-a']
    for suffix, structure in structures.items():
        token = tokens[f'smoke-owner-{suffix}']
        slug = structure['slug']
        request('GET', f'/forum/structures/{slug}')
        request('GET', f'/forum/structures/{slug}/dashboard', token)
        request('POST', f'/forum/structures/{slug}/documents', token, key=f'runtime-document-{suffix}', json={
            'title': f'PV interne {suffix.upper()} — test local', 'file_url': 'https://example.test/internal.pdf', 'visibility': 'STRUCTURE_MEMBERS'})
        request('POST', f'/forum/structures/{slug}/discussions', token, key=f'runtime-discussion-{suffix}', json={
            'title': 'Préparation locale', 'body': 'Message persisté par le smoke test réel.'})
        public = request('GET', f'/forum/structures/{slug}')
        assert 'PV interne' not in json.dumps(public)
    request('GET', f'/forum/structures/{a["slug"]}/documents', owner)
    request('GET', f'/forum/structures/{b["slug"]}/documents', owner, expected=403)
    request('GET', f'/forum/structures/{b["slug"]}/dashboard', owner, expected=403)
    request('GET', f'/forum/structures/{a["slug"]}/documents', expected=401)
    request('GET', f'/forum/structures/{a["slug"]}/documents', tokens['smoke-member'], expected=403)
    now = datetime.now(timezone.utc)
    event = request('POST', f'/forum/structures/{a["slug"]}/events', owner, key='runtime-event', json={
        'name': 'Soirée TORÈ — smoke local', 'bar_id': seed['bar_id'],
        'starts_at': (now-timedelta(minutes=10)).isoformat(), 'ends_at': (now+timedelta(hours=8)).isoformat(),
        'venue': 'Salle locale', 'description': 'Événement de validation locale, entrée libre.',
        'visibility': 'PRIVATE', 'publication_status': 'DRAFT',
    })
    event_id = event['id']
    request('PATCH', f'/forum/structures/{a["slug"]}/events/{event_id}', owner, key='runtime-event-publish', json={'visibility': 'PUBLIC', 'publication_status': 'PUBLISHED'})
    request('GET', f'/events/{event_id}/public')
    request('GET', '/events')
    request('GET', '/auth/me', owner)
    request('GET', '/me/profile', owner)
    request('GET', '/wallet/me', owner)
    partner = request('POST', '/partner/auth/login', json={'bar_id': seed['bar_id'], 'display_name': 'release-staff', 'pin': '1234'})
    request('GET', '/partner/portal/bar', partner['token'])
    request('GET', '/partner/portal/events', partner['token'])
    for origin in ['http://127.0.0.1:8080', 'http://127.0.0.1:5173', 'http://127.0.0.1:7357']:
        cors = client.options('/auth/me', headers={'Origin': origin, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization'})
        assert cors.status_code == 200 and cors.headers.get('access-control-allow-origin') == origin
    state = {'structures': structures, 'tokens': tokens, 'seed': seed, 'event_id': event_id}
    (ROOT / 'tore-backend/data/runtime-smoke-state.json').write_text(json.dumps(state), encoding='utf-8')
    print(json.dumps({'checks': checks, 'event_id': event_id, 'bar_id': seed['bar_id'], 'structure_a': a['slug'], 'structure_b': b['slug']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
