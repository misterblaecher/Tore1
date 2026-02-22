import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, ShieldCheck, ScanLine, Network, BookOpenText, Ticket, Building2, Lock } from "lucide-react";
import { Header, Footer } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  ANDROID_BETA_URL,
  DISPLAY_PHONE_NUMBER,
  FEEDBACK_URL,
  IOS_BETA_URL,
  WAITLIST_URL,
  WHATSAPP_URL,
} from "@/lib/external-links";

const modules = [
  {
    title: "Event Console",
    description: "Pilotage temps réel des flux, des accès et des points critiques de la soirée.",
    icon: Network,
  },
  {
    title: "Bar Kit",
    description: "Activation opérationnelle du bar: encaissement, contrôle, traçabilité et continuité terrain.",
    icon: ScanLine,
  },
  {
    title: "Tickets & Ledger",
    description: "Billetterie, transactions et journal unifié pour une mémoire exploitable de chaque événement.",
    icon: Ticket,
  },
  {
    title: "Comité OS",
    description: "Infrastructure dédiée aux comités pour standardiser l'exécution et la coordination inter-équipes.",
    icon: Building2,
  },
  {
    title: "Security & Compliance",
    description: "Socle sécurité, conformité et gouvernance des données à l'échelle territoriale.",
    icon: Lock,
  },
];

const roadmapPhases = [
  {
    phase: "Phase 0 — Fondations",
    badge: "Now",
    points: [
      "Identité unifiée et QR universel",
      "Modules activables ON/OFF",
      "Mode réseau faible par défaut",
      "Traçabilité opérationnelle minimale",
    ],
  },
  {
    phase: "Phase 1 — Console Comités",
    badge: "Now",
    points: [
      "Création d'event et cadrage terrain",
      "Entrée, comptage et flux live",
      "Rentabilité live par zone",
      "Canal urgence piloté",
    ],
  },
  {
    phase: "Phase 3 — Bar Kit",
    badge: "Next",
    points: ["Menu QR actionnable", "Zones QR par point de vente", "Tracking bar et continuité service"],
  },
  {
    phase: "Phase 4 — Commandes",
    badge: "Next",
    points: ["Commande QR multi-zones", "Statuts live de préparation", "Coordination comptoir et retrait"],
  },
  {
    phase: "Phase 5 — Tickets & Ledger",
    badge: "Later",
    points: ["Wallet opérationnel", "Top-up staff et gifts", "Ardoise optionnelle et ledger consolidé"],
  },
  {
    phase: "Phase 6 — Bets",
    badge: "Later",
    points: ["Formats auto-résolus", "Polymarket encadré", "Paramétrage comité et garde-fous"],
  },
  {
    phase: "Phase 7 — Hunts",
    badge: "Later",
    points: ["Mécaniques de hunts par zone", "Validation par checkpoints", "Exploitation des parcours terrain"],
  },
  {
    phase: "Phase 9 — Comité OS",
    badge: "Later",
    points: ["Forum interne", "Archives et passation", "Rôles, finances et gouvernance"],
  },
];

const deliverySteps = [
  "Module flag ON/OFF par event, bar ou comité.",
  "Déploiement en soirée test avec un seul module actif à la fois.",
  "Gating strict: OFF = invisible, FROZEN et READ_ONLY bloquent les writes.",
  "Logs et exports exploitables pour audit opérationnel minimal.",
  "Post-mortem court puis itération cadrée avant généralisation.",
];

const doneChecklist = [
  "Stable en réseau faible.",
  "Pas de double action côté interface (idempotence).",
  "UX claire avec bannières et raisons de blocage.",
  "Export basique et logs disponibles.",
  "Rollback possible via désactivation du module.",
];

const extensions = [
  {
    title: "Battles / Affonds",
    description: "Room join QR, formats encadrés, arbitre, anti-triche et ranking.",
  },
  {
    title: "Check-in boissons",
    description: "Badges, stats de consommation et paramètres de confidentialité.",
  },
  {
    title: "WiFi via QR",
    description: "Token temporaire avec expiration, revoke et journaux d'usage.",
  },
  {
    title: "Safe Kit",
    description: "Buddy, départ assisté, contacts d'urgence et incident discret.",
  },
  {
    title: "Carte & itinéraires",
    description: "Safe points, eau, toilettes et bars partenaires sur un plan actionnable.",
  },
  {
    title: "Calendrier guindailles",
    description: "Calendrier consolidé des soirées avec états et capacité estimée.",
  },
  {
    title: "Référentiel local / onboarding",
    description: "Glossaire opérationnel pour aligner rapidement nouveaux membres et équipes.",
  },
  {
    title: "Module organisation interne",
    description: "Baptême et planning interne avec règles de visibilité par rôle.",
  },
];

const API_URL = import.meta.env.VITE_API_URL?.trim();

type AccountRole = "student" | "committee" | "bar" | "dj";

const readUtmParams = () => {
  if (typeof window === "undefined") return undefined;
  const params = new URLSearchParams(window.location.search);
  const keys = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
  const utm = keys.reduce<Record<string, string>>((acc, key) => {
    const value = params.get(key);
    if (value) acc[key] = value;
    return acc;
  }, {});
  return Object.keys(utm).length ? utm : undefined;
};

const Index = () => {
  const { toast } = useToast();
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<AccountRole | "">("");
  const apiReady = Boolean(API_URL && API_URL.startsWith("http"));

  const scrollToWaitlist = () => {
    document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToContact = () => {
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
  };

  const copyPhoneNumber = async () => {
    try {
      await navigator.clipboard.writeText(DISPLAY_PHONE_NUMBER);
      toast({ title: "Copié", description: `Numéro ${DISPLAY_PHONE_NUMBER} copié.`, duration: 2400 });
    } catch {
      const textArea = document.createElement("textarea");
      textArea.value = DISPLAY_PHONE_NUMBER;
      textArea.setAttribute("readonly", "");
      textArea.style.position = "absolute";
      textArea.style.left = "-9999px";
      document.body.appendChild(textArea);
      textArea.select();

      const copied = document.execCommand("copy");
      document.body.removeChild(textArea);

      toast({
        title: copied ? "Copié" : "Copie indisponible",
        description: copied ? `Numéro ${DISPLAY_PHONE_NUMBER} copié.` : "Copiez manuellement le numéro affiché.",
        variant: copied ? "default" : "destructive",
        duration: 2400,
      });
    }
  };

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <Header />

      <main className="relative z-10">
        <section className="relative overflow-hidden pt-28 pb-20 md:pt-36 md:pb-28 border-b border-border/50 section-ember-texture">
          <div className="absolute inset-0 hero-heat-halo animate-halo-breathe" aria-hidden="true" />
          <svg className="absolute inset-0 h-full w-full opacity-70" viewBox="0 0 1600 820" fill="none" aria-hidden="true">
            <defs>
              <filter id="heroGlow" x="-40%" y="-40%" width="180%" height="180%" colorInterpolationFilters="sRGB">
                <feGaussianBlur stdDeviation="80" result="blur" />
              </filter>
              <radialGradient id="heroRadial" cx="50%" cy="34%" r="45%">
                <stop offset="0%" stopColor="rgba(255,179,71,0.34)" />
                <stop offset="45%" stopColor="rgba(255,90,31,0.22)" />
                <stop offset="100%" stopColor="rgba(11,11,11,0)" />
              </radialGradient>
            </defs>
            <circle cx="800" cy="210" r="300" fill="url(#heroRadial)" filter="url(#heroGlow)" />
          </svg>
          <div className="container relative z-10">
            <div className="max-w-4xl space-y-8 animate-fade-in">
              <p className="text-sm tracking-[0.2em] uppercase text-accent/90 font-semibold">Infrastructure territoriale</p>
              <h1 className="text-4xl leading-tight sm:text-5xl lg:text-7xl font-semibold tracking-tight">
                TORÈ — OS Numérique Territorial
              </h1>
              <p className="max-w-2xl text-base sm:text-lg text-muted-foreground leading-relaxed">
                TORÈ opère l'infrastructure digitale de l'écosystème étudiant liégeois: une base robuste pour exécuter, contrôler
                et capitaliser chaque événement.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 pt-2">
                <Button asChild size="lg" className="h-12 px-7 text-sm sm:text-base font-semibold">
                  <Link to="/#solution">Découvrir la plateforme</Link>
                </Button>
                <Button asChild size="lg" variant="outline" className="h-12 px-7 text-sm sm:text-base font-semibold border-accent/40 hover:bg-accent/10">
                  <a href={WHATSAPP_URL} target="_blank" rel="noreferrer">Accès Bar / Comité</a>
                </Button>
                <Button asChild size="lg" variant="ghost" className="h-12 px-7 text-sm sm:text-base font-semibold text-muted-foreground hover:text-foreground hover:bg-card/30">
                  <Link to="/#beta">Télécharger (Bêta)</Link>
                </Button>
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                {WAITLIST_URL ? (
                  <a href={WAITLIST_URL} target="_blank" rel="noreferrer" className="text-sm text-accent hover:text-accent/90 transition-colors">
                    Rejoindre la bêta
                  </a>
                ) : (
                  <button onClick={scrollToWaitlist} className="text-sm text-accent hover:text-accent/90 transition-colors text-left">
                    Rejoindre la bêta
                  </button>
                )}
                {FEEDBACK_URL ? (
                  <a href={FEEDBACK_URL} target="_blank" rel="noreferrer" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    Donner un feedback
                  </a>
                ) : (
                  <Link to="/#contact" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    Donner un feedback
                  </Link>
                )}
              </div>
              <Link to="/#contact" className="inline-flex text-sm text-muted-foreground hover:text-accent transition-colors">
                Contact ops →
              </Link>
            </div>
          </div>
        </section>

        <section id="probleme" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container">
            <div className="max-w-3xl space-y-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Problème structurel</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Un terrain actif, sans système d'exploitation opérationnel.</h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
                L'organisation reste fragmentée entre outils isolés, décisions locales et process hétérogènes. Sans OS dédié,
                les événements perdent en contrôle, en capacité d'exécution et en mémoire stratégique.
              </p>
            </div>
            <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                "Organisation fragmentée",
                "Pas d'OS opérationnel des événements",
                "Absence de mémoire exploitable",
                "Faible contrôle en temps réel",
              ].map((item) => (
                <div key={item} className="rounded-xl border border-border/60 bg-card/55 px-5 py-6 text-sm text-foreground/90 metal-edge-card">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="solution" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
            <div className="space-y-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Solution TORÈ</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Une infrastructure unifiée pour opérer le territoire étudiant.</h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
                TORÈ transforme les opérations événementielles en architecture maîtrisée: accès unifiés, modules activables,
                ledger consolidé et contrôle permanent.
              </p>
            </div>
            <div className="grid gap-4">
              {[
                { title: "QR universel d'entrée", icon: ScanLine },
                { title: "Activation modulaire des fonctions", icon: ShieldCheck },
                { title: "Ledger territorial", icon: BookOpenText },
                { title: "Contrôle opérationnel", icon: Network },
              ].map((item) => (
                <article key={item.title} className="rounded-xl border border-border/60 bg-background/60 p-5 flex items-start gap-4 metal-edge-card">
                  <item.icon className="mt-0.5 text-accent" size={20} />
                  <h3 className="font-medium text-base">{item.title}</h3>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="modules" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container">
            <div className="max-w-3xl mb-10 space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Modules</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Blocs opérationnels interconnectés.</h2>
            </div>
            <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-5">
              {modules.map((module) => (
                <article
                  key={module.title}
                  className="group rounded-xl border border-border/60 bg-card/40 p-6 min-h-44 transition-colors duration-300 hover:border-accent/40 metal-edge-card"
                >
                  <module.icon className="text-accent mb-4" size={22} />
                  <h3 className="text-lg font-semibold mb-2">{module.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{module.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="roadmap" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="max-w-3xl mb-10 space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Roadmap</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Déploiement phasé de l'OS territorial.</h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
                Déploiement par phases. Chaque module est activable (ON/OFF) et validé en conditions réelles.
              </p>
            </div>

            <div className="relative grid gap-5 md:grid-cols-2 xl:grid-cols-4">
              <div className="absolute left-3 top-1 bottom-1 w-px bg-gradient-to-b from-accent/50 via-accent/20 to-transparent md:hidden" aria-hidden="true" />
              {roadmapPhases.map((item) => (
                <article key={item.phase} className="relative ml-8 md:ml-0 rounded-xl border border-border/60 bg-background/70 p-5 metal-edge-card">
                  <div className="absolute -left-8 top-7 h-3 w-3 rounded-full border border-accent/60 bg-background md:hidden" aria-hidden="true" />
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <h3 className="text-lg font-semibold leading-tight">{item.phase}</h3>
                    <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent">
                      {item.badge}
                    </span>
                  </div>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    {item.points.map((point) => (
                      <li key={point} className="flex gap-2">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-accent/80 shrink-0" aria-hidden="true" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
            <p className="mt-6 text-sm text-muted-foreground">Extension layer ensuite: music, safe kit, carte, itinéraires et modules complémentaires.</p>
          </div>
        </section>

        <section id="delivery" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container grid gap-8 lg:grid-cols-[1.3fr_1fr] lg:gap-10 items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent mb-4">Méthode</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight mb-5">Méthode de livraison</h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed mb-8">
                Chaque feature est livrée module par module, testée en conditions terrain puis généralisée seulement après validation.
              </p>

              <div className="grid gap-4 md:grid-cols-2">
                {deliverySteps.map((step, index) => (
                  <article key={step} className="rounded-xl border border-border/60 bg-card/35 p-5 metal-edge-card">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent mb-3">Étape {index + 1}</p>
                    <p className="text-sm text-foreground/90 leading-relaxed">{step}</p>
                  </article>
                ))}
              </div>
            </div>

            <aside className="rounded-xl border border-accent/30 bg-[linear-gradient(145deg,rgba(255,179,71,0.06),rgba(11,11,11,0.86))] p-6 metal-edge-card">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent mb-4">Definition of Done</p>
              <ul className="space-y-3 text-sm text-muted-foreground">
                {doneChecklist.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-accent/80 shrink-0" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </section>

        <section id="extensions" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="max-w-3xl mb-10 space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Extensions</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Extensions terrain</h2>
              <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
                Modules additionnels activables. Priorisés après validation du socle.
              </p>
            </div>
            <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">
              {extensions.map((item) => (
                <article key={item.title} className="rounded-xl border border-border/60 bg-background/65 p-5 metal-edge-card">
                  <div className="mb-3">
                    <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent">
                      Extension
                    </span>
                  </div>
                  <h3 className="text-base font-semibold mb-2">{item.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="positioning" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-accent/20 bg-[linear-gradient(145deg,hsl(var(--card)/0.75),hsl(var(--background)))] p-8 md:p-12 metal-edge-card">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent mb-4">Positionnement stratégique</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight mb-6">TORÈ n'est pas une app. C'est une infrastructure.</h2>
              <p className="text-base md:text-lg text-muted-foreground leading-relaxed">
                La logique n'est pas de lancer un produit éphémère. La logique est de déployer un OS territorial durable, créant
                un standard d'exécution, un avantage cumulatif et un verrouillage long terme de la chaîne opérationnelle.
              </p>
            </div>
          </div>
        </section>



        <section id="beta" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
              <div className="space-y-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Accès bêta</p>
                <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Télécharger TORÈ (Bêta)</h2>
                <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
                  Déploiement progressif à Liège. Accès sur invitation pour bars et comités.
                </p>
                <p className="text-sm text-muted-foreground">
                  Si un lien n'est pas encore disponible, rejoignez la waitlist pour recevoir votre accès d'installation.
                </p>
                <Link to="/#account" className="inline-flex text-sm text-accent hover:text-accent/90 transition-colors">
                  Créer un compte TORÈ maintenant →
                </Link>
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/70 p-6 md:p-8 metal-edge-card space-y-4">
                <Button
                  asChild={Boolean(IOS_BETA_URL)}
                  onClick={IOS_BETA_URL ? undefined : scrollToWaitlist}
                  size="lg"
                  className="w-full h-12 font-semibold"
                >
                  {IOS_BETA_URL ? (
                    <a href={IOS_BETA_URL} target="_blank" rel="noreferrer">Télécharger iOS (Bêta)</a>
                  ) : (
                    <span>Télécharger iOS (Bêta)</span>
                  )}
                </Button>
                <Button
                  asChild={Boolean(ANDROID_BETA_URL)}
                  onClick={ANDROID_BETA_URL ? undefined : scrollToWaitlist}
                  size="lg"
                  variant="outline"
                  className="w-full h-12 font-semibold border-accent/40 hover:bg-accent/10"
                >
                  {ANDROID_BETA_URL ? (
                    <a href={ANDROID_BETA_URL} target="_blank" rel="noreferrer">Télécharger Android (Bêta)</a>
                  ) : (
                    <span>Télécharger Android (Bêta)</span>
                  )}
                </Button>
                {WAITLIST_URL ? (
                  <div className="pt-2">
                    <a href={WAITLIST_URL} target="_blank" rel="noreferrer" className="text-sm text-accent hover:text-accent/90 transition-colors">
                      Recevoir le lien d'installation →
                    </a>
                  </div>
                ) : (
                  <div className="pt-2 text-sm text-muted-foreground">Recevoir le lien d'installation via WhatsApp.</div>
                )}
              </div>
            </div>
          </div>
        </section>


        <section id="waitlist" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-border/60 bg-background/65 p-8 md:p-10 metal-edge-card space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Rejoindre la bêta</p>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">Waitlist pilotes TORÈ</h2>
              <p className="text-muted-foreground">Profils ciblés : Étudiant, Bar, Comité, DJ. Décrivez votre rôle et votre besoin pilote.</p>
              <p className="text-sm text-muted-foreground">Ce qu'on mesure : intérêt module et demandes de tests terrain.</p>
              <Link to="/#account" className="inline-flex text-sm text-accent hover:text-accent/90 transition-colors">
                Créer un compte TORÈ maintenant →
              </Link>
              {WAITLIST_URL ? (
                <Button asChild size="lg" className="h-12 px-7 text-sm sm:text-base font-semibold w-full sm:w-auto">
                  <a href={WAITLIST_URL} target="_blank" rel="noreferrer">Rejoindre la waitlist</a>
                </Button>
              ) : (
                <Button asChild size="lg" className="h-12 px-7 text-sm sm:text-base font-semibold w-full sm:w-auto">
                  <a href={WHATSAPP_URL} target="_blank" rel="noreferrer">Contact WhatsApp</a>
                </Button>
              )}
            </div>
          </div>
        </section>

        <section id="account" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-accent/25 bg-[linear-gradient(145deg,rgba(255,179,71,0.06),rgba(11,11,11,0.92))] p-8 md:p-10 metal-edge-card space-y-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Créer un compte</p>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">Créer un compte TORÈ</h2>
              <p className="text-muted-foreground">
                Onboarding opérationnel pour les profils étudiant, bar, DJ et comité. Chaque demande est revue sérieusement avant
                activation de l'accès.
              </p>

              <form
                className="grid gap-4 md:grid-cols-2"
                onSubmit={async (event: FormEvent<HTMLFormElement>) => {
                  event.preventDefault();
                  if (!API_URL || !API_URL.startsWith("http")) {
                    setAccountError("Backend non configuré.");
                    toast({ title: "Erreur", description: "Backend non configuré.", variant: "destructive", duration: 3200 });
                    return;
                  }

                  const accountRequestUrl = `${API_URL.replace(/\/+$/, "")}/public/account-request`;
                  setAccountError(null);
                  setAccountLoading(true);
                  const formData = new FormData(event.currentTarget);
                  const role = String(formData.get("role") || "") as AccountRole;
                  const payload = {
                    name: String(formData.get("name") || "").trim(),
                    email: String(formData.get("email") || "").trim(),
                    phone: String(formData.get("phone") || "").trim().replace(/\s+/g, ""),
                    is_whatsapp: formData.get("is_whatsapp") === "on",
                    role,
                    committee_name: role === "committee" ? String(formData.get("committee_name") || "").trim() || null : null,
                    source: "tore_site",
                    utm: readUtmParams(),
                  };

                  try {
                    console.debug(`Account request POST to: ${accountRequestUrl}`);
                    const response = await fetch(accountRequestUrl, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(payload),
                    });

                    if (!response.ok) {
                      const contentType = response.headers.get("content-type") || "";
                      const responseBody = contentType.includes("application/json")
                        ? await response.json().catch(() => null)
                        : await response.text().catch(() => "");
                      const backendMessage =
                        (typeof responseBody === "object" && responseBody
                          ? (responseBody as { detail?: { message?: string } | string; message?: string }).detail &&
                            typeof (responseBody as { detail?: { message?: string } | string }).detail === "object"
                            ? ((responseBody as { detail?: { message?: string } }).detail?.message ?? "")
                            : typeof (responseBody as { detail?: string }).detail === "string"
                              ? (responseBody as { detail?: string }).detail ?? ""
                              : (responseBody as { message?: string }).message ?? ""
                          : typeof responseBody === "string"
                            ? responseBody
                            : "") || "";
                      const messageByStatus: Record<number, string> = {
                        400: "Demande invalide. Vérifie les informations envoyées.",
                        422: "Certains champs sont invalides. Vérifie le formulaire.",
                        429: "Trop de tentatives. Réessaie un peu plus tard.",
                      };
                      const message = backendMessage || messageByStatus[response.status] || "Impossible d'enregistrer la demande.";
                      setAccountError(message);
                      toast({ title: "Erreur", description: message, variant: "destructive", duration: 3200 });
                      return;
                    }
                    event.currentTarget.reset();
                    setSelectedRole("");
                    toast({ title: "Compte enregistré", description: "Compte enregistré — on te contacte pour l’accès.", duration: 3200 });
                  } catch {
                    const message = "Erreur réseau. Réessaie dans un instant.";
                    setAccountError(message);
                    toast({ title: "Erreur", description: message, variant: "destructive", duration: 3200 });
                  } finally {
                    setAccountLoading(false);
                  }
                }}
              >
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Nom</span>
                  <input name="name" required className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Email</span>
                  <input type="email" name="email" required className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Téléphone</span>
                  <input type="tel" name="phone" required className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Rôle</span>
                  <select
                    name="role"
                    required
                    value={selectedRole}
                    onChange={(event) => setSelectedRole(event.target.value as AccountRole | "")}
                    className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                  >
                    <option value="">Sélectionner un rôle</option>
                    <option value="student">Étudiant</option>
                    <option value="committee">Comité</option>
                    <option value="bar">Bar</option>
                    <option value="dj">DJ</option>
                  </select>
                </label>
                {selectedRole === "committee" && (
                  <label className="md:col-span-2 space-y-2 text-sm">
                    <span className="text-foreground/90">Nom du comité</span>
                    <input name="committee_name" required={selectedRole === "committee"} className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                  </label>
                )}
                <label className="md:col-span-2 inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <input type="checkbox" name="is_whatsapp" className="h-4 w-4 rounded border-border bg-background/70 accent-[hsl(var(--accent))]" />
                  Ce numéro est WhatsApp
                </label>
                <div className="md:col-span-2 flex flex-col gap-2">
                  <Button type="submit" disabled={!apiReady || accountLoading} size="lg" className="h-11 px-6 text-sm font-semibold w-full sm:w-auto">
                    {accountLoading ? "Création en cours..." : "Créer mon compte"}
                  </Button>
                  {!apiReady && <span className="text-sm text-muted-foreground">Backend non configuré.</span>}
                  {accountError && <p className="text-sm text-destructive">{accountError}</p>}
                </div>
              </form>

              <p className="text-sm text-muted-foreground">
                Données utilisées uniquement pour l'onboarding compte TORÈ, conservation limitée et suppression sur demande.
              </p>
            </div>
          </div>
        </section>

        <section id="feedback" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-border/60 bg-background/65 p-8 md:p-10 metal-edge-card space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Feedback terrain</p>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">Donner un feedback opérationnel</h2>
              <p className="text-muted-foreground">Retour attendu : module testé, contexte, point de friction et amélioration prioritaire.</p>
              {FEEDBACK_URL ? (
                <Button asChild size="lg" variant="outline" className="h-12 px-7 text-sm sm:text-base font-semibold border-accent/40 hover:bg-accent/10 w-full sm:w-auto">
                  <a href={FEEDBACK_URL} target="_blank" rel="noreferrer">Envoyer un feedback</a>
                </Button>
              ) : (
                <Button asChild size="lg" variant="outline" className="h-12 px-7 text-sm sm:text-base font-semibold border-accent/40 hover:bg-accent/10 w-full sm:w-auto">
                  <a href={WHATSAPP_URL} target="_blank" rel="noreferrer">Feedback via WhatsApp</a>
                </Button>
              )}
            </div>
          </div>
        </section>

        <section className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-border/60 bg-background/65 p-8 md:p-10 metal-edge-card">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent mb-4">Tests terrain</p>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight mb-4">Tests modulaires à Liège — 1 module à la fois.</h2>
              <p className="text-muted-foreground leading-relaxed">
                Objectif : stabilité réseau faible, contrôle opérationnel et audit minimal avant généralisation.
              </p>
            </div>
          </div>
        </section>

        <section id="contact" className="py-16 md:py-24 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-accent/30 bg-[linear-gradient(135deg,rgba(11,11,11,0.95),rgba(28,16,10,0.96))] p-8 md:p-12 metal-edge-card">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent mb-4">Contact</p>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight mb-5">Contact</h2>
              <p className="max-w-2xl text-base md:text-lg text-muted-foreground leading-relaxed">
                Cellule ops TORÈ pour onboarding bar, coordination comité et mise en service terrain.
                Canal direct pour cadrage, activation et priorisation opérationnelle.
              </p>
              <div className="mt-8 flex flex-col sm:flex-row sm:items-center gap-4">
                <Button asChild size="lg" className="h-12 px-7 text-sm sm:text-base font-semibold">
                  <a href={WHATSAPP_URL} target="_blank" rel="noreferrer">
                    WhatsApp
                  </a>
                </Button>
                <Button onClick={copyPhoneNumber} size="lg" variant="outline" className="h-12 px-7 text-sm sm:text-base font-semibold border-accent/40 hover:bg-accent/10">
                  <Copy className="mr-2" size={16} />
                  Copier le numéro
                </Button>
              </div>
              <div className="mt-5 space-y-1 text-sm text-foreground/90">
                <p>WhatsApp: {DISPLAY_PHONE_NUMBER}</p>
                <p className="text-muted-foreground">Email bientôt.</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
};

export default Index;
