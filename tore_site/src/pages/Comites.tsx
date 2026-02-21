import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { 
  QrCode, 
  ArrowRight, 
  Calendar,
  Users,
  Timer,
  DollarSign,
  AlertTriangle,
  FileDown,
  Zap,
  Copy,
  Printer,
  UserCheck,
  Gauge,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  StopCircle,
  Menu,
  FileText,
  PieChart
} from "lucide-react";

const creationSteps = [
  {
    icon: Copy,
    title: "Choisir un template",
    description: "Soirée étudiante, gala, before, after… des configs prêtes à l'emploi.",
  },
  {
    icon: Calendar,
    title: "Configurer l'event",
    description: "Date, lieu, jauge max, prix entrée, options (vestiaire, conso…).",
  },
  {
    icon: Printer,
    title: "Générer les QR",
    description: "Pack QR pour entrée, bar, staff. Prêt à imprimer.",
  },
];

const countingFeatures = [
  {
    icon: UserCheck,
    title: "Scan entrée",
    description: "Chaque entrée est comptabilisée en temps réel.",
  },
  {
    icon: Gauge,
    title: "Jauge live",
    description: "Visualisez le remplissage vs la capacité max.",
  },
  {
    icon: Users,
    title: "Mode estimation",
    description: "Estimation intelligente si tous n'ont pas scanné.",
  },
];

const profitabilityItems = [
  {
    icon: TrendingUp,
    title: "Recettes estimées",
    description: "Entrées + consos + extras, mis à jour en temps réel.",
    color: "text-green-500",
  },
  {
    icon: TrendingDown,
    title: "Coûts",
    description: "Location, staff, boissons… tout est comptabilisé.",
    color: "text-red-500",
  },
  {
    icon: DollarSign,
    title: "Marge live",
    description: "Votre rentabilité en un coup d'œil.",
    color: "text-primary",
  },
];

const emergencyButtons = [
  {
    icon: Menu,
    title: "Menu only",
    description: "Désactive tout sauf le menu. Utile pour calmer le jeu.",
    severity: "warning",
  },
  {
    icon: StopCircle,
    title: "Stop hard",
    description: "Arrêt total des ventes et commandes. Urgence.",
    severity: "danger",
  },
  {
    icon: ShieldAlert,
    title: "Alerte staff",
    description: "Notification push à tout le staff immédiatement.",
    severity: "warning",
  },
];

const reportSections = [
  { icon: Users, label: "Entrées totales", value: "847" },
  { icon: DollarSign, label: "Recettes", value: "4 235 €" },
  { icon: TrendingUp, label: "Marge nette", value: "1 120 €" },
  { icon: Timer, label: "Pic d'affluence", value: "23h45" },
];

export default function Comites() {
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
                <Calendar className="text-primary" size={18} />
                <span className="text-sm font-medium">Pour les comités & events</span>
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Votre soirée,<br />
                <span className="text-primary neon-text">sous contrôle total</span>
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground mb-8">
                Créez un event en 2 minutes, gérez les entrées, suivez la rentabilité en live. 
                Tout ce dont un orga a besoin, sans prise de tête.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Créer un event démo
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

        {/* Création event < 2 min */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                <Zap className="text-primary" size={18} />
                <span className="text-sm font-medium">Création rapide</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Event créé en <span className="text-primary">moins de 2 min</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Des templates prêts à l'emploi, quelques clics, et votre event est configuré.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
              {creationSteps.map((step, index) => (
                <div key={step.title} className="relative">
                  <Card className="bg-card border-border hover:border-primary/50 transition-all h-full">
                    <CardContent className="p-6 text-center">
                      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                        <step.icon className="text-primary" size={32} />
                      </div>
                      <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                      <p className="text-muted-foreground text-sm">{step.description}</p>
                    </CardContent>
                  </Card>
                  {index < creationSteps.length - 1 && (
                    <ArrowRight className="hidden md:block absolute top-1/2 -right-4 transform -translate-y-1/2 text-primary/40" size={24} />
                  )}
                </div>
              ))}
            </div>

            {/* Templates preview */}
            <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-4xl mx-auto">
              {["Soirée étudiante", "Gala", "Before/After", "Festival"].map((template) => (
                <div 
                  key={template}
                  className="p-4 rounded-lg bg-card border border-border hover:border-primary/50 transition-all text-center cursor-pointer"
                >
                  <span className="font-medium">{template}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Entrée & Comptage */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Entrée & <span className="text-primary">Comptage</span>
                </h2>
                <p className="text-muted-foreground mb-8">
                  Suivez le remplissage en temps réel. Plus besoin de compter à la main 
                  ou de faire confiance aux estimations au doigt mouillé.
                </p>
                <div className="space-y-4">
                  {countingFeatures.map((feature) => (
                    <div key={feature.title} className="flex gap-4 p-4 rounded-xl bg-card border border-border">
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
              <div className="relative">
                <div className="max-w-sm mx-auto bg-card rounded-3xl border border-border p-6">
                  <div className="text-center mb-6">
                    <span className="text-sm text-muted-foreground">Jauge live</span>
                    <div className="text-5xl font-black text-primary mt-2">847</div>
                    <span className="text-muted-foreground">/ 1000 max</span>
                  </div>
                  <div className="w-full h-4 bg-surface rounded-full overflow-hidden mb-4">
                    <div className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-primary" style={{ width: '85%' }} />
                  </div>
                  <div className="flex justify-between text-sm text-muted-foreground">
                    <span>0</span>
                    <span className="text-yellow-500 font-medium">85%</span>
                    <span>1000</span>
                  </div>
                  <div className="mt-6 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                    <p className="text-sm text-yellow-500 text-center font-medium">
                      ⚠️ Approche de la jauge max
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Rentabilité Live */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Rentabilité <span className="text-primary">en temps réel</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Plus besoin d'attendre la fin de soirée pour savoir si vous êtes rentables. 
                Suivez vos chiffres en direct.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto">
              {profitabilityItems.map((item) => (
                <Card key={item.title} className="bg-card border-border">
                  <CardContent className="p-6 text-center">
                    <div className={`w-14 h-14 rounded-2xl bg-surface flex items-center justify-center mx-auto mb-4`}>
                      <item.icon className={item.color} size={28} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{item.title}</h3>
                    <p className="text-muted-foreground text-sm">{item.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Live dashboard preview */}
            <div className="mt-12 max-w-2xl mx-auto bg-card rounded-2xl border border-border p-6">
              <div className="flex items-center justify-between mb-6">
                <span className="font-bold">Dashboard live</span>
                <span className="text-xs text-green-500 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  En direct
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-surface">
                  <span className="text-sm text-muted-foreground">Recettes</span>
                  <div className="text-2xl font-bold text-green-500">4 235 €</div>
                </div>
                <div className="p-4 rounded-lg bg-surface">
                  <span className="text-sm text-muted-foreground">Coûts</span>
                  <div className="text-2xl font-bold text-red-500">3 115 €</div>
                </div>
                <div className="col-span-2 p-4 rounded-lg bg-primary/10 border border-primary/20">
                  <span className="text-sm text-muted-foreground">Marge nette</span>
                  <div className="text-3xl font-bold text-primary">+1 120 €</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Boutons d'urgence */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 border border-red-500/20 mb-6">
                <AlertTriangle className="text-red-500" size={18} />
                <span className="text-sm font-medium text-red-500">Sécurité</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Boutons <span className="text-primary">d'urgence</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                En cas de problème, reprenez le contrôle instantanément. 
                Un clic suffit pour sécuriser la situation.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {emergencyButtons.map((button) => (
                <Card 
                  key={button.title} 
                  className={`bg-card border-border ${button.severity === 'danger' ? 'hover:border-red-500/50' : 'hover:border-yellow-500/50'} transition-all`}
                >
                  <CardContent className="p-6 text-center">
                    <div className={`w-14 h-14 rounded-2xl ${button.severity === 'danger' ? 'bg-red-500/10' : 'bg-yellow-500/10'} flex items-center justify-center mx-auto mb-4`}>
                      <button.icon className={button.severity === 'danger' ? 'text-red-500' : 'text-yellow-500'} size={28} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{button.title}</h3>
                    <p className="text-muted-foreground text-sm">{button.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Rapport fin de soirée */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                  <FileDown className="text-primary" size={18} />
                  <span className="text-sm font-medium">Export automatique</span>
                </div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Rapport <span className="text-primary">fin de soirée</span>
                </h2>
                <p className="text-muted-foreground mb-6">
                  À la fin de l'event, recevez automatiquement un rapport complet. 
                  Parfait pour le débrief et la compta.
                </p>
                <ul className="space-y-3 mb-8">
                  {["Entrées par tranche horaire", "Recettes détaillées par poste", "Coûts et marge finale", "Incidents et alertes", "Export PDF et CSV"].map((item) => (
                    <li key={item} className="flex items-center gap-3">
                      <FileText className="text-primary shrink-0" size={18} />
                      <span className="text-muted-foreground">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="relative">
                <div className="max-w-sm mx-auto bg-card rounded-2xl border border-border overflow-hidden">
                  <div className="p-4 bg-primary/10 border-b border-border">
                    <div className="flex items-center justify-between">
                      <span className="font-bold">Rapport - Soirée BDE</span>
                      <PieChart className="text-primary" size={20} />
                    </div>
                    <span className="text-xs text-muted-foreground">15 janvier 2025</span>
                  </div>
                  <div className="p-4 space-y-3">
                    {reportSections.map((section) => (
                      <div key={section.label} className="flex items-center justify-between p-3 rounded-lg bg-surface">
                        <div className="flex items-center gap-2">
                          <section.icon className="text-muted-foreground" size={16} />
                          <span className="text-sm">{section.label}</span>
                        </div>
                        <span className="font-bold">{section.value}</span>
                      </div>
                    ))}
                  </div>
                  <div className="p-4 border-t border-border">
                    <Button className="w-full" variant="outline" size="sm">
                      <FileDown size={16} className="mr-2" />
                      Télécharger PDF
                    </Button>
                  </div>
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
                Prêt à organiser votre <span className="text-primary">prochaine soirée</span> ?
              </h2>
              <p className="text-muted-foreground mb-8">
                Créez votre premier event gratuitement et découvrez la puissance de TORÈ.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Créer un event démo
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
