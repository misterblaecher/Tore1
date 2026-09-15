"""Application composition entrypoint."""
from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_accounting import router as accounting
from app.routers.forum_event_workspace import router as event_workspace
from app.routers.forum_ownership import freeze_guard_middleware, router as ownership
from app.routers.structure_claims import router as claims
from app.routers.structure_claim_review import router as claim_review
from app.routers.structure_lifecycle import router as lifecycle
from app.routers.structure_rbac import router as rbac
from app.routers.structure_visibility import router as visibility
_REPLACED={("POST","/orgas"),("GET","/orgas/{org_id}"),("PUT","/orgas/{org_id}"),("PATCH","/forum/structures/{slug}/visibility")}; _MODULES={"app.legacy.monolith","app.routers.forum"}
def _has(app,m,p): return any(getattr(r,"path","")==p and m in (getattr(r,"methods",set()) or set()) for r in app.router.routes)
def _replace(app): app.router.routes[:]=[r for r in app.router.routes if not (getattr(getattr(r,"endpoint",None),"__module__","") in _MODULES and any((m,getattr(r,"path","")) in _REPLACED for m in (getattr(r,"methods",set()) or set())))]
def create_app():
    app=monolith.app; _replace(app); paths={getattr(r,"path","") for r in app.routes}
    if not any(p.endswith("/event-workspace") for p in paths): app.include_router(event_workspace)
    if not any(p.endswith("/accounting-summary") for p in paths): app.include_router(accounting)
    if not any(p.endswith("/publish") and p.startswith("/forum/structures/") for p in paths): app.include_router(lifecycle)
    if not _has(app,"GET","/forum/structures/{slug}/workspace"): app.include_router(rbac)
    if not _has(app,"PATCH","/forum/structures/{slug}/visibility"): app.include_router(visibility)
    if not getattr(app.state,"forum_ownership_installed",False): app.include_router(ownership); app.middleware("http")(freeze_guard_middleware); app.state.forum_ownership_installed=True
    if not any(p.startswith("/forum/structure-claims") for p in paths):
        claims.routes[:]=[r for r in claims.routes if getattr(getattr(r,"endpoint",None),"__name__","")!="review_structure_claim"]
        app.include_router(claim_review); app.include_router(claims)
    if not any(getattr(r,"name",None)=="upload_structure_file" for r in app.routes):
        from app.routers.storage import router as storage
        app.include_router(storage)
    if not any(getattr(r,"name",None)=="get_public_event_page" for r in app.routes):
        from app.routers.forum_events import router as events
        app.include_router(events)
    run_startup(app); return app
__all__=["create_app"]
