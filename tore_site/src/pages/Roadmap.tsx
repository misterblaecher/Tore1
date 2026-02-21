import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import UserAppRoadmap from "@/components/roadmap/UserAppRoadmap";
import PhonePreview from "@/components/roadmap/PhonePreview";
import { 
  ArrowRight, 
  Map,
  CheckCircle2,
  Circle,
  Clock,
  Zap,
  Users,
  Calendar,
  Beer,
  Brain,
  ShoppingCart,
  Ticket,
  Gamepad2,
  Target,
  Building2
} from "lucide-react";

const phases = [
  {
    phase: 0,
    title: "Fondations",
    status: "done",
    icon: Zap,
    description: "Architecture de base, auth, scanner QR, routing intelligent.",
    items: [
      "Infrastructure cloud scalable",
      "Système d'authentification sécurisé",
      "Scanner QR universel + routing",
      "Design system & composants UI",
    ],
  },
  {
    phase: 1,
    title: "MVP Comités Console",
    status: "done",
    icon: Users,
    description: "Création d'events, comptage, rentabilité live.",
    items: [
      "Templates d'events",
      "Gestion entrées & jauge",
      "Dashboard rentabilité temps réel",
      "Rapport fin de soirée",
    ],
  },
  {
    phase: 2,
    title: "Soirée complète",
    status: "current",
    icon: Calendar,
    description: "Workflow complet pour gérer une soirée de A à Z.",
    items: [
      "Rôles staff via QR",
      "Boutons d'urgence",
      "Mode réseau faible",
      "Notifications push",
    ],
  },
  {
    phase: 3,
    title: "Bar Kit + IA",
    status: "current",
    icon: Beer,
    description: "Outils complets pour bars avec options IA.",
    items: [
      "Menu QR riche",
      "Zones & tables",
      "Tracking analytics",
      "IA génération assets (optionnel)",
    ],
  },
  {
    phase: 4,
    title: "Commandes",
    status: "current",
    icon: ShoppingCart,
    description: "Prise de commande depuis la table, sans paiement obligatoire.",
    items: [
      "Panier client",
      "Notification staff",
      "Workflow cuisine/bar",
      "Historique commandes",
    ],
  },
  {
    phase: 5,
    title: "Tickets & Paiement",
    status: "planned",
    icon: Ticket,
    description: "Billetterie intégrée et paiement sécurisé.",
    items: [
      "Vente de tickets",
      "Paiement intégré (Stripe)",
      "Préventes & promos",
      "Cash-out organisateurs",
    ],
  },
  {
    phase: 6,
    title: "Bets",
    status: "planned",
    icon: Gamepad2,
    description: "Paris sociaux entre amis, sans argent réel.",
    items: [
      "Création de paris",
      "Système de points",
      "Classements & badges",
      "Challenges de groupe",
    ],
  },
  {
    phase: 7,
    title: "Hunts",
    status: "planned",
    icon: Target,
    description: "Chasses et défis gamifiés pour animer les soirées.",
    items: [
      "Création de hunts",
      "QR cachés / checkpoints",
      "Récompenses",
      "Leaderboards",
    ],
  },
  {
    phase: 8,
    title: "OS Bar",
    status: "planned",
    icon: Building2,
    description: "Suite complète pour gérer un bar de A à Z.",
    items: [
      "Inventaire & stocks",
      "Planning staff",
      "Comptabilité intégrée",
      "Multi-établissements",
    ],
  },
];

const getStatusStyles = (status: string) => {
  switch (status) {
    case "done":
      return {
        bg: "bg-green-500/10",
        border: "border-green-500/30",
        text: "text-green-500",
        icon: CheckCircle2,
        label: "Terminé",
      };
    case "current":
      return {
        bg: "bg-primary/10",
        border: "border-primary/30",
        text: "text-primary",
        icon: Clock,
        label: "En cours",
      };
    case "upcoming":
      return {
        bg: "bg-yellow-500/10",
        border: "border-yellow-500/30",
        text: "text-yellow-500",
        icon: Circle,
        label: "Bientôt",
      };
    default:
      return {
        bg: "bg-muted/10",
        border: "border-muted/30",
        text: "text-muted-foreground",
        icon: Circle,
        label: "Planifié",
      };
  }
};

export default function Roadmap() {
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
                <Map className="text-primary" size={18} />
                <span className="text-sm font-medium">Roadmap</span>
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Notre vision,<br />
                <span className="text-primary neon-text">étape par étape</span>
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground mb-8">
                TORÈ évolue constamment. Voici notre plan pour transformer l'expérience nightlife, 
                une phase à la fois.
              </p>
            </div>
          </div>
        </section>

        {/* Philosophy */}
        <section className="py-12 bg-surface/50">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <p className="text-lg text-muted-foreground">
                <span className="text-primary font-semibold">Notre approche :</span> le MVP prouve l'adoption bar + la valeur comité 
                <span className="text-foreground font-medium"> avant </span> 
                les modules "argent". On construit sur du solide.
              </p>
            </div>
          </div>
        </section>

        {/* Timeline */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-4xl mx-auto">
              {/* Legend */}
              <div className="flex flex-wrap gap-4 justify-center mb-12">
                {[
                  { status: "done", label: "Terminé" },
                  { status: "current", label: "En cours" },
                  { status: "upcoming", label: "Bientôt" },
                  { status: "planned", label: "Planifié" },
                ].map((item) => {
                  const styles = getStatusStyles(item.status);
                  return (
                    <div key={item.status} className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${styles.bg} border ${styles.border}`} />
                      <span className="text-sm text-muted-foreground">{item.label}</span>
                    </div>
                  );
                })}
              </div>

              {/* Timeline items */}
              <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-6 md:left-1/2 top-0 bottom-0 w-px bg-border md:-translate-x-px" />

                <div className="space-y-8">
                  {phases.map((phase, index) => {
                    const styles = getStatusStyles(phase.status);
                    const StatusIcon = styles.icon;
                    const isEven = index % 2 === 0;

                    return (
                      <div 
                        key={phase.phase}
                        className={`relative flex items-start gap-6 md:gap-12 ${
                          isEven ? "md:flex-row" : "md:flex-row-reverse"
                        }`}
                      >
                        {/* Content */}
                        <div className={`flex-1 ml-16 md:ml-0 ${isEven ? "md:text-right" : "md:text-left"}`}>
                          <div className={`inline-block p-6 rounded-2xl ${styles.bg} border ${styles.border}`}>
                            <div className={`flex items-center gap-3 mb-3 ${isEven ? "md:flex-row-reverse" : ""}`}>
                              <div className={`w-10 h-10 rounded-xl ${styles.bg} flex items-center justify-center`}>
                                <phase.icon className={styles.text} size={20} />
                              </div>
                              <div>
                                <span className={`text-xs font-medium ${styles.text}`}>Phase {phase.phase}</span>
                                <h3 className="text-xl font-bold">{phase.title}</h3>
                              </div>
                            </div>
                            <p className="text-muted-foreground text-sm mb-4">{phase.description}</p>
                            <ul className={`space-y-2 ${isEven ? "md:text-right" : "md:text-left"}`}>
                              {phase.items.map((item) => (
                                <li key={item} className={`flex items-center gap-2 text-sm ${isEven ? "md:flex-row-reverse" : ""}`}>
                                  <CheckCircle2 className={`shrink-0 ${phase.status === "done" ? "text-green-500" : "text-muted-foreground/50"}`} size={14} />
                                  <span className={phase.status === "done" ? "text-foreground" : "text-muted-foreground"}>{item}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        {/* Center node */}
                        <div className="absolute left-6 md:left-1/2 md:-translate-x-1/2 w-12 h-12 rounded-full bg-background border-4 border-border flex items-center justify-center z-10">
                          <StatusIcon className={styles.text} size={20} />
                        </div>

                        {/* Spacer for alignment */}
                        <div className="hidden md:block flex-1" />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Phone Preview */}
        <PhonePreview />

        {/* UI User Roadmap */}
        <UserAppRoadmap />

        {/* MVP Focus */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <div className="text-center mb-12">
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  MVP <span className="text-primary">#1</span> : Ce qu'on ship
                </h2>
                <p className="text-muted-foreground">
                  Les fonctionnalités core disponibles dès maintenant.
                </p>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                {[
                  "Scanner QR universel",
                  "Event comités (template + pack QR)",
                  "Entrée & comptage temps réel",
                  "Rentabilité live + rapport",
                  "Bar kit (menu + zones + tracking)",
                  "Rôles staff via QR + révocation",
                ].map((feature) => (
                  <div key={feature} className="flex items-center gap-3 p-4 rounded-xl bg-card border border-border">
                    <CheckCircle2 className="text-green-500 shrink-0" size={20} />
                    <span className="font-medium">{feature}</span>
                  </div>
                ))}
              </div>

              <div className="mt-8 p-6 rounded-xl bg-muted/10 border border-border">
                <h3 className="font-bold mb-3 text-muted-foreground">Plus tard :</h3>
                <div className="flex flex-wrap gap-2">
                  {["Tickets", "Paiements", "Cash-out", "Bets", "Hunts"].map((feature) => (
                    <span key={feature} className="px-3 py-1 rounded-full bg-muted text-muted-foreground text-sm">
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Envie de <span className="text-primary">participer</span> ?
              </h2>
              <p className="text-muted-foreground mb-8">
                Rejoignez les early adopters et aidez-nous à construire le futur de la nightlife.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Demander une démo
                    <ArrowRight size={18} />
                  </Button>
                </Link>
                <Link to="/pricing">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    Voir les tarifs
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
