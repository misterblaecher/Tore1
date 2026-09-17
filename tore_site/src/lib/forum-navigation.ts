import { Archive, BarChart3, BookOpen, CalendarDays, Clock3, FileText, Globe2, Image, KeyRound, LayoutDashboard, LockKeyhole, MessageSquare, ShieldCheck, SlidersHorizontal, Users, WalletCards } from "lucide-react";

export const forumNavGroups = [
  { label: "Général", items: [["dashboard", "Dashboard", LayoutDashboard], ["public", "Page publique", Globe2]] },
  { label: "Organisation", items: [["discussions", "Discussions", MessageSquare], ["channel-acls", "Accès salons", LockKeyhole], ["events", "Événements", CalendarDays], ["members", "Membres", Users], ["planning", "Planning", Clock3]] },
  { label: "Mémoire", items: [["documents", "Documents", FileText], ["albums", "Albums", Image], ["archives", "Archives", Archive], ["folklore", "Folklore", BookOpen]] },
  { label: "Gestion", items: [["stats", "Stats soirées", BarChart3], ["accounting", "Comptabilité", WalletCards], ["ownership", "Ownership", KeyRound], ["visibility", "Visibilité", SlidersHorizontal], ["audit", "Audit logs", ShieldCheck]] },
] as const;
type ForumNavItem = (typeof forumNavGroups)[number]["items"][number];
export const forumNavItems = forumNavGroups.flatMap<ForumNavItem>((group) => group.items);
export const structureTypeLabels: Record<string, string> = { COMMITTEE: "Comité", CIRCLE: "Cercle", ORDER: "Ordre", BAR: "Bar partenaire", ASSOCIATION: "Association", PARTNER: "Structure partenaire", OTHER: "Structure" };
export const forumRoleLabels: Record<string, string> = { OWNER: "Propriétaire", PRESIDENT: "Président", VICE_PRESIDENT: "Vice-président", ADMIN: "Administrateur", MANAGER: "Gestionnaire", TREASURER: "Trésorier", SECRETARY: "Secrétaire", MEMBER: "Membre", STAFF: "Équipe", COMMUNICATION: "Communication", ARCHIVIST: "Archiviste", BUREAU: "Bureau" };
export function structurePath(slug: string, section = "dashboard") { return `/forum/structures/${encodeURIComponent(slug)}${section === "public" ? "" : `/${section}`}`; }
export type ForumWorkspace = { id: number; slug: string; name: string; type: string; city?: string | null; logoUrl?: string | null; role: string; canManage: boolean; canReadFinance: boolean };
export type ForumNavigationContext = { workspace?: ForumWorkspace; loading: boolean; error: boolean };
