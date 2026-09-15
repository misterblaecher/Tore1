import { useEffect, useMemo, useState, type FormEvent } from "react";
import { LockKeyhole, ShieldCheck } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";

type Channel = { id: number; name: string; visibility: string; aclExplicit?: boolean };
type AclOptions = {
  roles: { id: number; name: string }[];
  capabilities: string[];
  members: { userId: string; displayName: string }[];
};
type ChannelAcl = {
  channelId: number;
  enabled: boolean;
  legacyVisibility: string;
  roleIds: number[];
  capabilities: string[];
  memberUserIds: string[];
  options: AclOptions;
};
const v2Base = (slug: string) => `/forum/v2/structures/${encodeURIComponent(slug)}`;

export default function ChannelAclSettings({ slug }: { slug: string }) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [acl, setAcl] = useState<ChannelAcl | null>(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void apiFetch<{ items: Channel[] }>(`${v2Base(slug)}/channel-acl-options`)
      .then((response) => {
        if (!active) return;
        setChannels(response.items);
        setSelectedId((current) => current ?? response.items[0]?.id ?? null);
        setError("");
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof ApiError ? reason.message : "Impossible de charger les salons à configurer."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [slug]);

  useEffect(() => {
    if (!selectedId) { setAcl(null); return; }
    let active = true;
    setLoading(true); setSaved(false);
    void apiFetch<ChannelAcl>(`${v2Base(slug)}/channels/${selectedId}/acl`)
      .then((response) => { if (active) { setAcl(response); setError(""); } })
      .catch((reason: unknown) => { if (active) setError(reason instanceof ApiError ? reason.message : "Impossible de charger l’ACL du salon."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [slug, selectedId]);

  const visibleMembers = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!acl || !needle) return acl?.options.members ?? [];
    return acl.options.members.filter((member) => `${member.displayName} ${member.userId}`.toLowerCase().includes(needle));
  }, [acl, filter]);

  const toggle = <T,>(values: T[], value: T) => values.includes(value) ? values.filter((item) => item !== value) : [...values, value];

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!acl || !selectedId || saving) return;
    setSaving(true); setError(""); setSaved(false);
    try {
      const response = await apiFetch<ChannelAcl>(`${v2Base(slug)}/channels/${selectedId}/acl`, {
        method: "PUT",
        body: JSON.stringify({ enabled: acl.enabled, role_ids: acl.roleIds, capabilities: acl.capabilities, member_user_ids: acl.memberUserIds }),
      });
      setAcl(response);
      setChannels((current) => current.map((channel) => channel.id === selectedId ? { ...channel, aclExplicit: response.enabled } : channel));
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Impossible d’enregistrer l’ACL du salon.");
    } finally { setSaving(false); }
  }

  return <section className="forum-card">
    <div className="forum-section-title"><div><span className="forum-eyebrow">Discussions internes</span><h2>ACL par salon</h2></div><ShieldCheck size={20} /></div>
    <p className="forum-muted">Autorisez précisément des rôles, des capabilities ou des membres. Les trois listes sont combinées en <strong>OU</strong>. Une ACL explicite vide ferme le salon à tous sauf l’Owner.</p>
    {error ? <p className="forum-alert" role="alert">{error}</p> : null}
    {!channels.length && !loading ? <p className="forum-empty">Aucun salon à configurer.</p> : null}
    {channels.length ? <form className="forum-form" onSubmit={save}>
      <label>Salon<select value={selectedId ?? ""} onChange={(event) => setSelectedId(Number(event.target.value))}>{channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}{channel.aclExplicit ? " · ACL" : ""}</option>)}</select></label>
      {acl ? <>
        <label className="portal-editor-wide"><span className="forum-inline"><input type="checkbox" checked={acl.enabled} onChange={(event) => { setAcl({ ...acl, enabled: event.target.checked }); setSaved(false); }} /><LockKeyhole size={16} /> Activer l’ACL explicite pour ce salon</span><small className="forum-muted">Désactivée : compatibilité avec le niveau {acl.legacyVisibility}. Activée : seuls les grants ci-dessous (et l’Owner) donnent accès.</small></label>
        <fieldset disabled={!acl.enabled || saving} className="portal-editor-wide"><legend>Rôles autorisés</legend><div className="portal-editor-blocks">{acl.options.roles.map((role) => <label key={role.id}><input type="checkbox" checked={acl.roleIds.includes(role.id)} onChange={() => { setAcl({ ...acl, roleIds: toggle(acl.roleIds, role.id) }); setSaved(false); }} />{role.name}</label>)}</div></fieldset>
        <fieldset disabled={!acl.enabled || saving} className="portal-editor-wide"><legend>Capabilities autorisées</legend><div className="portal-editor-blocks">{acl.options.capabilities.map((capability) => <label key={capability}><input type="checkbox" checked={acl.capabilities.includes(capability)} onChange={() => { setAcl({ ...acl, capabilities: toggle(acl.capabilities, capability) }); setSaved(false); }} /><code>{capability}</code></label>)}</div></fieldset>
        <fieldset disabled={!acl.enabled || saving} className="portal-editor-wide"><legend>Membres ajoutés explicitement</legend><label>Filtrer les membres<input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Nom du membre…" /></label><div className="portal-editor-blocks">{visibleMembers.map((member) => <label key={member.userId}><input type="checkbox" checked={acl.memberUserIds.includes(member.userId)} onChange={() => { setAcl({ ...acl, memberUserIds: toggle(acl.memberUserIds, member.userId) }); setSaved(false); }} />{member.displayName}</label>)}</div></fieldset>
        <div className="forum-inline"><button className="forum-button forum-button--primary" type="submit" disabled={saving}>{saving ? "Enregistrement…" : "Enregistrer les accès"}</button>{saved ? <span className="forum-muted" role="status">ACL enregistrée. Les accès sont recalculés immédiatement côté serveur.</span> : null}</div>
      </> : loading ? <p className="forum-muted">Chargement de l’ACL…</p> : null}
    </form> : null}
  </section>;
}
