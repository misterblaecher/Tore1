export type PortalBlock = "about" | "events" | "services" | "team" | "gallery" | "memory" | "partners";
export type PortalContent = { about: string; opening_hours: string; services: string[]; announcement: string; hidden_blocks: PortalBlock[] };
export type PortalStructure = {
  id?: number; name: string; slug: string; type: string; description?: string | null;
  city?: string | null; address?: string | null; contactEmail?: string | null; contactPhone?: string | null;
  websiteUrl?: string | null; instagramHandle?: string | null; socialLinks?: Record<string, string>;
  logoUrl?: string | null; bannerUrl?: string | null; primaryColor?: string | null;
  history?: string | null; sponsors?: string[]; portal?: Partial<PortalContent>;
};
export type PortalEvent = { id: number; name: string; startsAt?: string | null; venue?: string | null; city?: string | null; description?: string | null; bannerUrl?: string | null };
export type PortalAlbum = { id: number; title: string; description?: string | null; coverUrl?: string | null; media?: { id: number; url: string; type?: string; caption?: string | null }[] };
export type PublicPortal = {
  structure: PortalStructure; visibility: Record<string, string>; events: PortalEvent[];
  members: { id: number; displayName: string; avatarUrl?: string | null; role: string; mandateLabel?: string | null }[];
  albums: PortalAlbum[];
  pages: { id: number; title: string; category: string; content?: string; publishedAt?: string | null }[];
};
export const portalBlockLabels: Record<PortalBlock, string> = { about: "À propos", events: "Événements à venir", services: "Activités & services", team: "Équipe / Comité", gallery: "Galerie", memory: "Histoire / Folklore", partners: "Partenaires" };
export const defaultPortal: PortalContent = { about: "", opening_hours: "", services: [], announcement: "", hidden_blocks: [] };

export function portalVariant(type: string) {
  const standard: PortalBlock[] = ["about", "events", "services", "team", "gallery", "memory"];
  switch (type) {
    case "COMMITTEE": return { label: "Comité", team: "Comité actuel", intro: "Les événements, les visages et la mémoire de votre comité.", order: standard };
    case "CIRCLE": return { label: "Cercle", team: "Comité du cercle", intro: "Une identité, des rencontres et des traditions partagées.", order: standard };
    case "ORDER": return { label: "Ordre", team: "Membres & responsables", intro: "L’histoire, les traditions et la transmission de l’ordre.", order: ["about", "memory", "team", "events", "gallery", "services"] as PortalBlock[] };
    case "BAR": return { label: "Bar partenaire", team: "L’équipe", intro: "Les soirées, les activités et les informations du lieu.", order: standard };
    case "ASSOCIATION": return { label: "Association", team: "L’équipe", intro: "Les missions, les projets et les personnes qui les portent.", order: ["about", "services", "events", "team", "gallery", "memory"] as PortalBlock[] };
    case "PARTNER": return { label: "Structure partenaire", team: "Équipe & référents", intro: "Une structure engagée dans la communauté TORÈ.", order: standard };
    default: return { label: "Structure", team: "Le collectif", intro: "Les rencontres et la mémoire de la structure.", order: standard };
  }
}

export function publicWebUrl(value?: string | null): string | undefined {
  if (!value) return undefined;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : undefined; } catch { return undefined; }
}
export function publicImageUrl(value?: string | null): string | undefined {
  return value?.startsWith("/") && !value.startsWith("//") ? value : publicWebUrl(value);
}
