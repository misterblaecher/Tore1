import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { 
  QrCode, 
  ArrowRight, 
  Menu,
  MapPin,
  BarChart3,
  ShoppingCart,
  CheckCircle2,
  Clock,
  Image,
  Tag,
  Layers,
  Printer,
  Eye,
  MousePointer,
  TrendingUp,
  Bell,
  ChefHat
} from "lucide-react";

const menuFeatures = [
  {
    icon: Menu,
    title: "Carte complète",
    description: "Catégories, sous-catégories, filtres (végé, sans gluten…).",
  },
  {
    icon: Image,
    title: "Visuels attractifs",
    description: "Photos haute qualité, descriptions qui donnent envie.",
  },
  {
    icon: Tag,
    title: "Prix & Promos",
    description: "Happy hours, formules, prix barrés automatiques.",
  },
  {
    icon: Layers,
    title: "Multi-cartes",
    description: "Carte du jour, cocktails, brunch… changez en un clic.",
  },
];

const zoneFeatures = [
  {
    icon: MapPin,
    title: "Zones définies",
    description: "Terrasse, salle, bar, VIP… chaque zone a son QR.",
  },
  {
    icon: Printer,
    title: "Pack QR imprimable",
    description: "Générez vos QR en PDF, prêts à imprimer et plastifier.",
  },
  {
    icon: Layers,
    title: "Numéros de table",
    description: "Associez chaque QR à une table pour le suivi.",
  },
];

const trackingMetrics = [
  {
    icon: Eye,
    title: "Scans",
    description: "Nombre de scans par zone, heure, jour.",
  },
  {
    icon: MousePointer,
    title: "Vues items",
    description: "Quels plats/cocktails sont les plus consultés.",
  },
  {
    icon: TrendingUp,
    title: "Conversions",
    description: "Du scan à l'ajout panier (si commandes activées).",
  },
  {
    icon: BarChart3,
    title: "Tendances",
    description: "Évolution sur la semaine, le mois, comparatifs.",
  },
];

const orderFeatures = [
  {
    icon: ShoppingCart,
    title: "Panier client",
    description: "Le client compose sa commande depuis son téléphone.",
  },
  {
    icon: Bell,
    title: "Notification staff",
    description: "Alerte en temps réel sur l'app staff ou tablette.",
  },
  {
    icon: ChefHat,
    title: "Validation cuisine/bar",
    description: "Workflow simple : reçu → en cours → prêt.",
  },
];

const onboardingChecklist = [
  { step: 1, title: "Créer votre compte", time: "1 min" },
  { step: 2, title: "Importer ou créer votre carte", time: "3 min" },
  { step: 3, title: "Définir vos zones", time: "2 min" },
  { step: 4, title: "Générer les QR codes", time: "1 min" },
  { step: 5, title: "Imprimer et placer", time: "3 min" },
];

export default function Bars() {
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
                <QrCode className="text-primary" size={18} />
                <span className="text-sm font-medium">Pour les bars</span>
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Votre bar,<br />
                <span className="text-primary neon-text">digitalisé en 10 min</span>
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground mb-8">
                Menu QR moderne, zones intelligentes, tracking précis. 
                Tout ce qu'il faut pour optimiser votre service sans complexité.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Tester sur mon bar
                    <ArrowRight size={18} />
                  </Button>
                </Link>
                <Link to="/produit">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    Voir le produit
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Menu QR */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Menu QR <span className="text-primary">riche mais léger</span>
                </h2>
                <p className="text-muted-foreground mb-8">
                  Une carte digitale qui charge instantanément, même en réseau faible. 
                  Belle, pratique, et qui donne envie de commander.
                </p>
                <div className="grid sm:grid-cols-2 gap-4">
                  {menuFeatures.map((feature) => (
                    <div key={feature.title} className="flex gap-3 p-4 rounded-lg bg-card border border-border">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                        <feature.icon className="text-primary" size={20} />
                      </div>
                      <div>
                        <h3 className="font-semibold mb-1">{feature.title}</h3>
                        <p className="text-sm text-muted-foreground">{feature.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="relative">
                <div className="aspect-[3/4] max-w-sm mx-auto bg-gradient-to-br from-card to-surface rounded-3xl border border-border p-6 flex flex-col">
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-bold text-lg">🍺 Le Bar</span>
                    <span className="text-xs text-muted-foreground">Terrasse</span>
                  </div>
                  <div className="space-y-3 flex-1">
                    {["Cocktails", "Bières", "Vins", "Soft", "Snacks"].map((cat, i) => (
                      <div key={cat} className="p-3 rounded-lg bg-surface-hover flex items-center justify-between">
                        <span className="font-medium">{cat}</span>
                        <ArrowRight size={16} className="text-muted-foreground" />
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/20 text-center">
                    <span className="text-sm text-primary font-medium">Happy Hour -30%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Zones & QR */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Zones & <span className="text-primary">Packs QR</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Chaque zone de votre établissement peut avoir son propre QR, 
                pour un tracking précis et une expérience client optimale.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {zoneFeatures.map((feature) => (
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

        {/* Tracking */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Tracking <span className="text-primary">temps réel</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Comprenez comment vos clients interagissent avec votre menu. 
                Des données actionnables, pas juste des chiffres.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
              {trackingMetrics.map((metric) => (
                <Card key={metric.title} className="bg-card border-border hover:border-primary/50 transition-all">
                  <CardContent className="p-6 text-center">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                      <metric.icon className="text-primary" size={24} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{metric.title}</h3>
                    <p className="text-muted-foreground text-sm">{metric.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Commandes (optionnel) */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div className="order-2 lg:order-1">
                <div className="grid gap-4">
                  {orderFeatures.map((feature, index) => (
                    <div 
                      key={feature.title} 
                      className="flex gap-4 p-5 rounded-xl bg-card border border-border hover:border-primary/50 transition-all"
                    >
                      <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <feature.icon className="text-primary" size={24} />
                      </div>
                      <div>
                        <h3 className="font-bold mb-1">{feature.title}</h3>
                        <p className="text-sm text-muted-foreground">{feature.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="order-1 lg:order-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-500/10 border border-yellow-500/20 mb-4">
                  <span className="text-xs font-medium text-yellow-500">Module optionnel</span>
                </div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Commandes <span className="text-primary">sans friction</span>
                </h2>
                <p className="text-muted-foreground mb-6">
                  Permettez à vos clients de commander depuis leur table. 
                  Sans paiement obligatoire — activez uniquement ce dont vous avez besoin.
                </p>
                <p className="text-sm text-muted-foreground italic">
                  💡 Idéal pour réduire les temps d'attente et optimiser le service en salle.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Checklist Onboarding */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="max-w-2xl mx-auto">
              <div className="text-center mb-12">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                  <Clock className="text-primary" size={18} />
                  <span className="text-sm font-medium">Setup en 10 minutes</span>
                </div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Checklist <span className="text-primary">onboarding</span>
                </h2>
                <p className="text-muted-foreground">
                  De zéro à opérationnel en moins de 10 minutes. Promis.
                </p>
              </div>

              <div className="space-y-4">
                {onboardingChecklist.map((item) => (
                  <div 
                    key={item.step}
                    className="flex items-center gap-4 p-4 rounded-xl bg-card border border-border"
                  >
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                      <span className="font-bold text-primary">{item.step}</span>
                    </div>
                    <div className="flex-1">
                      <span className="font-medium">{item.title}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Clock size={14} />
                      {item.time}
                    </div>
                    <CheckCircle2 className="text-green-500" size={20} />
                  </div>
                ))}
              </div>

              <div className="mt-8 p-6 rounded-xl bg-primary/10 border border-primary/20 text-center">
                <p className="text-lg font-bold mb-2">Total : ~10 minutes</p>
                <p className="text-sm text-muted-foreground">
                  Et votre bar est live. On vous accompagne si besoin.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Prêt à <span className="text-primary">tester</span> ?
              </h2>
              <p className="text-muted-foreground mb-8">
                Créez votre compte gratuitement et digitalisez votre bar en quelques minutes.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Tester sur mon bar
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
