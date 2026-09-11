export class IntegrityError extends Error{
  constructor(message='Intégrité refusée',code='INTEGRITY_ERROR'){super(message);this.name='IntegrityError';this.code=code}
}
export class AuthenticationError extends Error{
  constructor(message='Authentification requise'){super(message);this.name='AuthenticationError';this.code='AUTH_REQUIRED'}
}
export class ValidationError extends Error{
  constructor(message='Donnée invalide',field=null){super(message);this.name='ValidationError';this.code='VALIDATION_ERROR';this.field=field}
}
export const IMMUTABLE_FIELDS=Object.freeze(['id','structureId','createdAt']);
export function assertNoImmutable(input,fields=IMMUTABLE_FIELDS){
  if(!input||typeof input!=='object')return;
  for(const key of fields)if(Object.prototype.hasOwnProperty.call(input,key))throw new IntegrityError(`Champ immuable interdit : ${key}`,'IMMUTABLE_FIELD');
}
export function pickAllowed(input,allowed,{rejectUnknown=true,immutable=IMMUTABLE_FIELDS}={}){
  input=input&&typeof input==='object'?input:{};assertNoImmutable(input,immutable);const allow=new Set(allowed),out={};
  for(const [k,v] of Object.entries(input)){if(!allow.has(k)){if(rejectUnknown)throw new IntegrityError(`Champ non autorisé : ${k}`,'UNKNOWN_FIELD');continue}out[k]=v}
  return out;
}
export function parseRequiredDate(value,label='Date'){
  if(value===null||value===undefined||String(value).trim()==='')throw new ValidationError(`${label} requise`,label);
  const d=value instanceof Date?new Date(value):new Date(String(value));if(Number.isNaN(d.getTime()))throw new ValidationError(`${label} invalide`,label);return d.toISOString();
}
export function parseOptionalDate(value,label='Date'){
  if(value===null||value===undefined||String(value).trim()==='')return null;return parseRequiredDate(value,label);
}
export function parseNonNegativeNumber(value,label='Valeur',{integer=false,max=1_000_000_000,allowNull=false}={}){
  if((value===null||value===undefined||String(value).trim()==='')&&allowNull)return null;
  if(value===null||value===undefined||String(value).trim()==='')throw new ValidationError(`${label} requise`,label);
  const n=Number(value);if(!Number.isFinite(n))throw new ValidationError(`${label} invalide`,label);if(n<0)throw new ValidationError(`${label} ne peut pas être négative`,label);if(n>max)throw new ValidationError(`${label} trop élevée`,label);if(integer&&!Number.isInteger(n))throw new ValidationError(`${label} doit être un entier`,label);return n;
}
export function requireAuthenticatedUser(repo){const id=repo.state.currentUserId;if(!id||!repo.state.users?.some(u=>u.id===id))throw new AuthenticationError();return id}
