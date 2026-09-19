"""Application composition entrypoint."""
from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.event_manager import router as event_manager
from app.routers.forum_accounting import router as accounting
from app.routers.forum_event_workspace import router as event_workspace
from app.routers.forum_ownership import freeze_guard_middleware, router as ownership
from app.routers.forum_invitations import router as invitations_legacy
from app.routers.forum_invitations_rbac import router as invitations_rbac
from app.routers.forum_channel_acl_current import router as channel_acl
from app.routers.structure_claims import router as claims
from app.routers.structure_claim_review import router as claim_review
from app.routers.structure_lifecycle import router as lifecycle
from app.routers.structure_rbac import router as rbac
from app.routers.structure_visibility import router as visibility
from app.routers.structure_seo import router as seo
from app.routers.forum_planning import router as planning
from app.routers.forum_search import router as search
from app.routers.forum_notifications import router as notifications
from app.routers.forum_directory import router as directory
from app.services.event_cohosting_operational import install_cohost_operational_access
from app.routers.web_auth import router as web_auth

_REPLACED={("POST","/orgas"),("GET","/orgas/{org_id}"),("PUT","/orgas/{org_id}"),("PATCH","/forum/structures/{slug}/visibility")}
_MODULES={"app.legacy.monolith","app.routers.forum"}
_FORUM_ENDPOINT_REPLACED={"list_structures","list_discussions","create_discussion","update_discussion","list_documents"}
_INVITE_REPLACED={"list_structure_invitations","create_structure_invitation","resend_structure_invitation","revoke_structure_invitation","accept_structure_invitation"}

def _has(app,m,p): return any(getattr(r,"path","")==p and m in (getattr(r,"methods",set()) or set()) for r in app.router.routes)

def _enable_credentialed_web_cors(app):
    """Allow explicit TORÈ origins to send the web refresh cookie; never trust wildcard preview origins."""
    for middleware in app.user_middleware:
        if getattr(getattr(middleware, "cls", None), "__name__", "") == "CORSMiddleware":
            middleware.kwargs["allow_credentials"] = True
            middleware.kwargs["allow_origin_regex"] = None
    app.middleware_stack = None
def _replace(app):
    kept=[]
    for r in app.router.routes:
        module=getattr(getattr(r,"endpoint",None),"__module__",""); name=getattr(getattr(r,"endpoint",None),"__name__",""); path=getattr(r,"path",""); methods=getattr(r,"methods",set()) or set()
        if module in _MODULES and any((m,path) in _REPLACED for m in methods): continue
        if module=="app.routers.forum" and name in _FORUM_ENDPOINT_REPLACED: continue
        kept.append(r)
    app.router.routes[:]=kept

def create_app():
    app=monolith.app; _replace(app); _enable_credentialed_web_cors(app); install_cohost_operational_access(); paths={getattr(r,"path","") for r in app.routes}
    if not any(p.endswith("/event-workspace") for p in paths): app.include_router(event_workspace)
    if not any(p.endswith("/accounting-summary") for p in paths): app.include_router(accounting)
    if not any(p.endswith("/event-manager") for p in paths): app.include_router(event_manager)
    if not any(p.endswith("/publish") and p.startswith("/forum/structures/") for p in paths): app.include_router(lifecycle)
    if not _has(app,"GET","/forum/structures/{slug}/workspace"): app.include_router(rbac)
    if not _has(app,"PATCH","/forum/structures/{slug}/visibility"): app.include_router(visibility)
    if not _has(app,"GET","/forum/seo/structures/{slug}"): app.include_router(seo)
    if not _has(app,"GET","/forum/structures/{slug}/planning"): app.include_router(planning)
    if not _has(app,"GET","/forum/structures/{slug}/search"): app.include_router(search)
    if not _has(app,"GET","/forum/structures/{slug}/notifications"): app.include_router(notifications)
    if not _has(app,"GET","/forum/structures"): app.include_router(directory)
    if not getattr(app.state,"forum_ownership_installed",False): app.include_router(ownership); app.middleware("http")(freeze_guard_middleware); app.state.forum_ownership_installed=True
    if not getattr(app.state,"forum_claims_installed",False):
        claims.routes[:]=[r for r in claims.routes if getattr(getattr(r,"endpoint",None),"__name__","")!="review_structure_claim"]
        app.include_router(claim_review); app.include_router(claims); app.state.forum_claims_installed=True
    if not getattr(app.state,"forum_invitations_installed",False):
        invitations_legacy.routes[:]=[r for r in invitations_legacy.routes if getattr(getattr(r,"endpoint",None),"__name__","") not in _INVITE_REPLACED]
        app.include_router(invitations_rbac); app.include_router(invitations_legacy); app.state.forum_invitations_installed=True
    if not getattr(app.state,"forum_channel_acl_installed",False): app.include_router(channel_acl); app.state.forum_channel_acl_installed=True
    if not any(getattr(r,"name",None)=="upload_structure_file" for r in app.routes):
        from app.routers.storage import router as storage
        app.include_router(storage)
    if not any(getattr(r,"name",None)=="get_public_event_page" for r in app.routes):
        from app.routers.forum_events import router as events
        app.include_router(events)
    if not _has(app,"POST","/auth/web/refresh"): app.include_router(web_auth)
    run_startup(app); return app
__all__=["create_app"]
