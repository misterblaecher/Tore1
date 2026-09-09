export const siteNavigation = [
  { label: "Accueil", href: "/" },
  { label: "L’application", href: "/produit" },
  { label: "Pour les comités", href: "/comites" },
  { label: "Roadmap", href: "/roadmap" },
  { label: "Contact", href: "/contact" },
];

// Preserve links shared before the presentation was split into dedicated pages.
export const legacySiteAnchors: Record<string, string> = {
  "#solution": "/produit", "#probleme": "/produit", "#modules": "/produit",
  "#positioning": "/produit", "#roadmap": "/roadmap", "#delivery": "/roadmap",
  "#extensions": "/roadmap", "#beta": "/rejoindre#beta", "#waitlist": "/rejoindre#waitlist",
  "#account": "/rejoindre#account", "#contact": "/contact", "#feedback": "/contact",
};
