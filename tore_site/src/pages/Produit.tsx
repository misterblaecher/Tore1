import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { 
  ArrowRight, 
  CalendarSearch,
  Sparkles,
  BookOpenText,
  Landmark,
  ToggleRight,
  Shield,
  Users,
  Crown,
  WifiOff,
  Database,
  RefreshCw,
  Globe,
  BarChart3,
  FileDown,
  Settings
} from "lucide-react";

const productPillars = [
  {
    step: "01",
    icon: CalendarSearch,
    title: "Découvrir",
    description: "Soirées proches dans le Carré, soirées à venir et filtres par bar, comité, type, date ou proximité.",
  },
  {
    step: "02",
    icon: Sparkles,
    title: "Vivre",
    description: "Polymarket, défis, mini-jeux, classements, cadeaux P2P et interactions sociales en soirée.",
  },
  {
    step: "03",
    icon: BookOpenText,
    title: "Se souvenir",
    description: "Profil, historique des soirées, badges, appartenance comité et mémoire collective de guindaille.",
  },
];

const modulesList = [
  {
    icon: CalendarSearch,
    title: "Découverte soirées",
    description: "Autour de soi, à venir, détail avant de rejoindre.",
    active: true,
  },
  {
    icon: Users,
    title: "Entrée & Comptage",
    description: "Gestion des entrées, jauge temps réel, estimations.",
    active: true,
  },
  {
    icon: BarChart3,
    title: "Dynamisation live",
    description: "Polymarket, défis, classements, ticker utile.",
    active: true,
  },
  {
    icon: Landmark,
    title: "Vie comité",
    description: "Forum, annonces, archives, traditions.",
    active: true,
  },
  {
    icon: Settings,
    title: "Commandes & wallet",
    description: "Paiement interne, cadeaux P2P, statuts.",
    active: false,
  },
  {
    icon: Crown,
    title: "Mémoire guindaille",
    description: "Badges, historique, appartenance, recap.",
    active: false,
  },
];

const roles = [
  { name: "Owner", description: "Contrôle total, facturation, suppression", color: "text-primary" },
  { name: "Manager", description: "Gestion quotidienne, staff, exports", color: "text-yellow-500" },
  { name: "Staff", description: "Actions opérationnelles limitées", color: "text-blue-500" },
  { name: "Viewer", description: "Lecture seule, dashboards", color: "text-muted-foreground" },
];

const offlineFeatures = [
  {
    icon: Database,
    title: "Cache intelligent",
    description: "Les données critiques sont pré-chargées et disponibles offline.",
  },
  {
    icon: RefreshCw,
    title: "Sync automatique",
    description: "Dès que le réseau revient, tout se synchronise en background.",
  },
  {
    icon: WifiOff,
    title: "Mode dégradé",
    description: "Fonctionnalités essentielles maintenues même sans connexion.",
  },
];

const portalFeatures = [
  {
    icon: Settings,
    title: "Gestion menu",
    description: "Créer, éditer, organiser votre carte en quelques clics.",
  },
  {
    icon: Globe,
    title: "Lieux & modules",
    description: "Configurer identité du lieu, modules actifs et actions contextuelles.",
  },
  {
    icon: BarChart3,
    title: "Analytics",
    description: "Dashboards temps réel : participation, modules, ventes, interactions.",
  },
  {
    icon: FileDown,
    title: "Exports",
    description: "Rapports PDF, CSV pour comptabilité et analyse.",
  },
];

export default function Produit() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <StickyCTA />
      
      <main className="pt-24">
        {/* Hero */}
        <section className="py-16 md:py-24 relative overflow-hidden">
          <div className="absolute inset-0 gradient-radial opacity-30" />
          <div className="container relative z-10">
            <div className="text-center max-w-3xl mx-auto">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                <Sparkles className="text-primary" size={18} />
                <span className="text-sm font-medium">Le produit</span>
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Découvrir, vivre,<br />
                <span className="text-primary neon-text">se souvenir</span>
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground mb-8">
                TORÈ relie soirées, bars, comités, folklore et profil personnel.
                Le QR reste un raccourci utile, mais l’expérience commence par la découverte.
              </p>
            </div>
          </div>
        </section>

        {/* Produit - 3 piliers */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Un parcours <span className="text-primary">soirée-first</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                L’utilisateur choisit une soirée, comprend le contexte, puis rejoint avec le bon niveau d’engagement.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
              {productPillars.map((step, index) => (
                <div key={step.step} className="relative">
                  <Card className="bg-card border-border hover:border-primary/50 transition-all h-full">
                    <CardContent className="p-6 text-center">
                      <div className="text-5xl font-black text-primary/20 mb-4">{step.step}</div>
                      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                        <step.icon className="text-primary" size={32} />
                      </div>
                      <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                      <p className="text-muted-foreground text-sm">{step.description}</p>
                    </CardContent>
                  </Card>
                  {index < productPillars.length - 1 && (
                    <ArrowRight className="hidden md:block absolute top-1/2 -right-4 transform -translate-y-1/2 text-primary/40" size={24} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Modules ON/OFF */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Modules <span className="text-primary">ON/OFF</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Activez uniquement ce dont vous avez besoin. Pas d'usine à gaz, que de la valeur.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
              {modulesList.map((module) => (
                <Card 
                  key={module.title}
                  className={`bg-card border-border transition-all ${module.active ? 'hover:border-primary/50' : 'opacity-60'}`}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                        <module.icon className="text-primary" size={24} />
                      </div>
                      <div className={`flex items-center gap-2 text-xs font-medium ${module.active ? 'text-green-500' : 'text-muted-foreground'}`}>
                        <ToggleRight size={16} />
                        {module.active ? 'MVP' : 'Bientôt'}
                      </div>
                    </div>
                    <h3 className="text-lg font-bold mb-2">{module.title}</h3>
                    <p className="text-muted-foreground text-sm">{module.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Rôles & Permissions */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Rôles & <span className="text-primary">Permissions</span>
                </h2>
                <p className="text-muted-foreground mb-8">
                  Chaque membre de l'équipe a exactement les droits dont il a besoin. 
                  Attribuez des rôles via QR, révoquez en un clic.
                </p>
                <div className="space-y-4">
                  {roles.map((role) => (
                    <div key={role.name} className="flex items-center gap-4 p-4 rounded-lg bg-card border border-border">
                      <div className={`font-bold ${role.color}`}>{role.name}</div>
                      <div className="text-sm text-muted-foreground">{role.description}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="relative">
                <div className="aspect-square max-w-md mx-auto bg-gradient-to-br from-primary/20 to-transparent rounded-3xl flex items-center justify-center">
                  <div className="text-center p-8">
                    <Shield className="w-24 h-24 text-primary mx-auto mb-4 animate-pulse-glow" />
                    <p className="text-xl font-bold">Sécurité granulaire</p>
                    <p className="text-muted-foreground text-sm mt-2">
                      QR signés, expiration auto, audit trail
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Mode réseau faible */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                <WifiOff className="text-primary" size={18} />
                <span className="text-sm font-medium">Soirée-proof</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Mode <span className="text-primary">réseau faible</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                La 4G lâche en pleine soirée ? Pas de panique. TORÈ continue de fonctionner.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {offlineFeatures.map((feature) => (
                <Card key={feature.title} className="bg-card border-border hover:border-primary/50 transition-all">
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                      <feature.icon className="text-primary" size={28} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{feature.title}</h3>
                    <p className="text-muted-foreground text-sm">{feature.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Portail Web */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Portail <span className="text-primary">Web</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Gérez tout depuis votre navigateur. Lieux, modules, analytics, exports.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto mb-12">
              {portalFeatures.map((feature) => (
                <Card key={feature.title} className="bg-card border-border hover:border-primary/50 transition-all">
                  <CardContent className="p-6 text-center">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                      <feature.icon className="text-primary" size={24} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{feature.title}</h3>
                    <p className="text-muted-foreground text-sm">{feature.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* CTAs */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Prêt à <span className="text-primary">digitaliser</span> votre lieu ?
              </h2>
              <p className="text-muted-foreground mb-8">
                Choisissez votre parcours : faire vivre un lieu, publier une soirée ou structurer un comité.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/bars">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Onboard mon bar
                    <ArrowRight size={18} />
                  </Button>
                </Link>
                <Link to="/comites">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    Créer un event
                    <ArrowRight size={18} />
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
