from sqlalchemy.orm import Session
from db import engine
from models import OrganizationMembership
from tests.test_forum_structure_mvp import client, setup_function, _guest, _headers


def test_explicit_channel_acl_filters_feed_search_and_direct_post_access():
    owner, owner_id = _guest("ACL owner")
    allowed, allowed_id = _guest("ACL allowed")
    denied, denied_id = _guest("ACL denied")
    org = client.post("/orgas", json={"name":"ACL Structure","org_type":"COMMITTEE"}, headers=_headers(owner,"acl-org")).json()["orga"]
    with Session(engine) as db:
        db.add_all([
            OrganizationMembership(organization_id=org["id"],user_id=allowed_id,role="MEMBER",status="ACTIVE",created_by_user_id=owner_id),
            OrganizationMembership(organization_id=org["id"],user_id=denied_id,role="MEMBER",status="ACTIVE",created_by_user_id=owner_id),
        ]); db.commit()
    base=f'/forum/structures/{org["slug"]}'
    channel=client.post(base+"/channels",json={"name":"Secret ACL","visibility":"STRUCTURE_MEMBERS"},headers=_headers(owner,"acl-channel")).json()["id"]
    post=client.post(base+"/discussions",json={"title":"secret-marker","body":"private searchable body","channel_id":channel},headers=_headers(owner,"acl-post")).json()
    policy=client.put(base+f"/channels/{channel}/acl",json={"enabled":True,"role_ids":[],"capabilities":[],"member_user_ids":[allowed_id]},headers=_headers(owner,"acl-policy"))
    assert policy.status_code==200 and policy.json()["enabled"] is True
    allowed_feed=client.get(base+"/discussions?search=secret-marker",headers=_headers(allowed)).json()
    assert [x["id"] for x in allowed_feed["posts"]]==[post["id"]]
    denied_feed=client.get(base+"/discussions?search=secret-marker",headers=_headers(denied)).json()
    assert denied_feed["posts"]==[]
    assert all(x["id"]!=channel for x in denied_feed["channels"])
    denied_direct=client.patch(base+f'/discussions/{post["id"]}',json={"emoji":"👍","active":True},headers=_headers(denied,"acl-direct"))
    assert denied_direct.status_code==404
    owner_feed=client.get(base+"/discussions?search=secret-marker",headers=_headers(owner)).json()
    assert owner_feed["posts"][0]["id"]==post["id"]
