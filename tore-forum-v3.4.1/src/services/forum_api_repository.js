const DEFAULT_BASE_URL = '/forum/v2';

export function forumBackendEnabled(){
  const meta = document.querySelector('meta[name="tore-forum-backend"]')?.content;
  if(meta != null) return ['1','true','yes','on'].includes(String(meta).toLowerCase());
  return window.TORE_FORUM_BACKEND_ENABLED === true;
}

function defaultTokenProvider(){
  // The host application should inject the existing TORÈ bearer token.  The
  // adapter deliberately does not invent a second Forum identity/session.
  if(typeof window.TORE_AUTH_TOKEN_PROVIDER === 'function') return window.TORE_AUTH_TOKEN_PROVIDER();
  return window.TORE_AUTH_TOKEN || null;
}

export class ForumApiError extends Error{
  constructor(status, body){
    super(body?.detail?.reason || body?.detail || body?.reason || `HTTP ${status}`);
    this.name='ForumApiError';
    this.status=status;
    this.body=body;
  }
}

export class ForumApiRepository{
  constructor({baseUrl=DEFAULT_BASE_URL, tokenProvider=defaultTokenProvider}={}){
    this.baseUrl=String(baseUrl).replace(/\/$/,'');
    this.tokenProvider=tokenProvider;
  }

  async request(path,{method='GET',body,headers={},signal}={}){
    const token=await this.tokenProvider?.();
    const requestHeaders={Accept:'application/json',...headers};
    if(token) requestHeaders.Authorization=`Bearer ${token}`;
    if(body !== undefined && !(body instanceof FormData)) requestHeaders['Content-Type']='application/json';
    const response=await fetch(`${this.baseUrl}${path}`,{
      method,headers:requestHeaders,signal,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      credentials:'same-origin',
    });
    if(response.status===204)return null;
    const type=response.headers.get('content-type')||'';
    const payload=type.includes('application/json')?await response.json():await response.blob();
    if(!response.ok)throw new ForumApiError(response.status,payload);
    return payload;
  }

  health(){return this.request('/health')}
  meStructures(){return this.request('/me/structures')}
  context(slug){return this.request(`/structures/${encodeURIComponent(slug)}/context`)}
  updateStructure(slug,patch){return this.request(`/structures/${encodeURIComponent(slug)}`,{method:'PATCH',body:patch})}
  setPublicPage(slug,patch){return this.request(`/structures/${encodeURIComponent(slug)}/public-page`,{method:'PATCH',body:patch})}
  members(slug){return this.request(`/structures/${encodeURIComponent(slug)}/members`)}
  updateMember(slug,id,patch){return this.request(`/structures/${encodeURIComponent(slug)}/members/${id}`,{method:'PATCH',body:patch})}
  roles(slug){return this.request(`/structures/${encodeURIComponent(slug)}/roles`)}
  createRole(slug,data){return this.request(`/structures/${encodeURIComponent(slug)}/roles`,{method:'POST',body:data})}
  updateRole(slug,id,patch){return this.request(`/structures/${encodeURIComponent(slug)}/roles/${id}`,{method:'PATCH',body:patch})}
  visibility(slug){return this.request(`/structures/${encodeURIComponent(slug)}/visibility`)}
  setVisibility(slug,policy){return this.request(`/structures/${encodeURIComponent(slug)}/visibility`,{method:'PUT',body:policy})}
  events(slug){return this.request(`/structures/${encodeURIComponent(slug)}/events`)}
  createEvent(slug,data){return this.request(`/structures/${encodeURIComponent(slug)}/events`,{method:'POST',body:data})}
  transitionEvent(slug,id,target,idempotencyKey=crypto.randomUUID()){
    return this.request(`/structures/${encodeURIComponent(slug)}/events/${id}/transition`,{method:'POST',body:{target},headers:{'Idempotency-Key':idempotencyKey}})
  }
  transferOwnership(slug,newOwnerUserId,idempotencyKey=crypto.randomUUID()){
    return this.request(`/structures/${encodeURIComponent(slug)}/ownership/transfer`,{method:'POST',body:{new_owner_user_id:newOwnerUserId},headers:{'Idempotency-Key':idempotencyKey}})
  }
  channels(slug){return this.request(`/structures/${encodeURIComponent(slug)}/channels`)}
  messages(slug,channelId){return this.request(`/structures/${encodeURIComponent(slug)}/channels/${channelId}/messages`)}
  postMessage(slug,channelId,data){return this.request(`/structures/${encodeURIComponent(slug)}/channels/${channelId}/messages`,{method:'POST',body:data})}
  documents(slug,q=''){return this.request(`/structures/${encodeURIComponent(slug)}/documents${q?`?q=${encodeURIComponent(q)}`:''}`)}
  async uploadDocumentVersion(slug,documentId,file){const form=new FormData();form.append('file',file);return this.request(`/structures/${encodeURIComponent(slug)}/documents/${documentId}/versions`,{method:'POST',body:form})}
  albums(slug){return this.request(`/structures/${encodeURIComponent(slug)}/albums`)}
  folklore(slug){return this.request(`/structures/${encodeURIComponent(slug)}/folklore`)}
  posts(slug){return this.request(`/structures/${encodeURIComponent(slug)}/posts`)}
  stats(slug,eventId){return this.request(`/structures/${encodeURIComponent(slug)}/stats${eventId?`?event_id=${eventId}`:''}`)}
  accounting(slug){return this.request(`/structures/${encodeURIComponent(slug)}/accounting`)}
  audit(slug){return this.request(`/structures/${encodeURIComponent(slug)}/audit`)}
  search(slug,q){return this.request(`/structures/${encodeURIComponent(slug)}/search?q=${encodeURIComponent(q)}`)}

  publicStructure(slug){return this.request(`/public/structures/${encodeURIComponent(slug)}`)}
  publicEvents(slug){return this.request(`/public/structures/${encodeURIComponent(slug)}/events`)}
  publicAlbums(slug){return this.request(`/public/structures/${encodeURIComponent(slug)}/albums`)}
  publicFolklore(slug){return this.request(`/public/structures/${encodeURIComponent(slug)}/folklore`)}
  publicPosts(slug){return this.request(`/public/structures/${encodeURIComponent(slug)}/posts`)}
}

export function createForumApiRepository(options){return new ForumApiRepository(options)}
