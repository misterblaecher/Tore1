from fastapi.testclient import TestClient


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_role_upgrade_request_and_admin_approval(monkeypatch):
    monkeypatch.setenv('ORGA_CODE', 'orga-secret')
    monkeypatch.setenv('TEAM_CODE', 'team-secret')
    monkeypatch.setenv('ADMIN_API_KEY', 'admin-secret')

    import importlib
    import main
    importlib.reload(main)
    main.ensure_seed()

    client = TestClient(main.app)
    guest = client.post('/auth/guest', json={'display_name': 'role-user'})
    token = guest.json()['token']

    denied = client.patch('/auth/me', json={'account_mode': 'organizer'}, headers=_auth_headers(token))
    assert denied.status_code == 403

    bad = client.post('/auth/role/request-upgrade', json={'requested_mode': 'organizer', 'code': 'bad'}, headers=_auth_headers(token))
    assert bad.status_code == 403

    created = client.post('/auth/role/request-upgrade', json={'requested_mode': 'organizer', 'code': 'orga-secret'}, headers=_auth_headers(token))
    assert created.status_code == 200
    req_id = created.json()['request']['id']

    pending = client.get('/admin/role-requests?status=pending', headers={'X-Admin-Api-Key': 'admin-secret'})
    assert pending.status_code == 200
    assert any(row['id'] == req_id for row in pending.json()['items'])

    approved = client.patch(f'/admin/role-requests/{req_id}', json={'action': 'approve'}, headers={'X-Admin-Api-Key': 'admin-secret'})
    assert approved.status_code == 200
    assert approved.json()['request']['status'] == 'approved'

    me = client.get('/auth/me', headers=_auth_headers(token))
    assert me.status_code == 200
    assert me.json()['account_mode'] == 'organizer'
