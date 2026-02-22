import { Link } from "react-router-dom";
import { Copy, ShieldCheck, ScanLine, Network, BookOpenText, Ticket, Building2, Lock } from "lucide-react";
import { Header, Footer } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

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

const whatsappUrl = "https://wa.me/qr/RJBBQE34G3ALI1";
const phoneNumber = "+3249560497";

const Index = () => {
  const { toast } = useToast();

  const copyPhoneNumber = async () => {
    try {
      await navigator.clipboard.writeText(phoneNumber);
      toast({ title: "Copié", description: `Numéro ${phoneNumber} copié.` });
    } catch {
      toast({ title: "Copie indisponible", description: "Copiez manuellement le numéro affiché.", variant: "destructive" });
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
                  <Link to="/bars">Accès Bar / Comité</Link>
                </Button>
              </div>
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

        <section id="positionnement" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
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
                  <a href={whatsappUrl} target="_blank" rel="noreferrer">
                    WhatsApp
                  </a>
                </Button>
                <Button onClick={copyPhoneNumber} size="lg" variant="outline" className="h-12 px-7 text-sm sm:text-base font-semibold border-accent/40 hover:bg-accent/10">
                  <Copy className="mr-2" size={16} />
                  Copier le numéro
                </Button>
              </div>
              <div className="mt-5 space-y-1 text-sm text-foreground/90">
                <p>WhatsApp: {phoneNumber}</p>
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
