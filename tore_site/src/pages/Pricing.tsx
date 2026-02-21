import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { 
  ArrowRight, 
  Check,
  X,
  Sparkles,
  Zap,
  Crown,
  MessageSquare,
  Brain,
  DollarSign,
  Users
} from "lucide-react";

const plans = [
  {
    name: "Free",
    description: "Pour découvrir TORÈ",
    price: "0€",
    period: "/mois",
    popular: false,
    icon: Zap,
    features: [
      { name: "Menu QR basique", included: true },
      { name: "Tracking scans", included: true },
      { name: "1 événement / mois", included: true },
      { name: "Comptage entrées", included: true },
      { name: "Rapport fin de soirée", included: true },
      { name: "Zones & tables", included: false },
      { name: "Exports CSV/PDF", included: false },
      { name: "Rôles staff illimités", included: false },
      { name: "Mode commandes", included: false },
      { name: "Support prioritaire", included: false },
    ],
    cta: "Commencer gratuitement",
    ctaVariant: "outline" as const,
  },
  {
    name: "Pro Bar",
    description: "Pour les établissements",
    price: "49€",
    period: "/mois",
    popular: true,
    icon: Crown,
    features: [
      { name: "Menu QR riche + visuels", included: true },
      { name: "Tracking analytics complet", included: true },
      { name: "Événements illimités", included: true },
      { name: "Comptage entrées", included: true },
      { name: "Rapport fin de soirée", included: true },
      { name: "Zones & tables illimitées", included: true },
      { name: "Exports CSV/PDF", included: true },
      { name: "Rôles staff illimités", included: true },
      { name: "Mode commandes", included: true },
      { name: "Support prioritaire", included: true },
    ],
    cta: "Essayer Pro",
    ctaVariant: "default" as const,
  },
];

const addons = [
  {
    icon: Brain,
    name: "IA Assets",
    description: "Génération automatique de visuels et descriptions pour vos menus.",
    price: "+19€/mois",
    status: "Bientôt",
  },
  {
    icon: DollarSign,
    name: "Modules Money",
    description: "Paiements intégrés, billetterie, cash-out organisateurs.",
    price: "Sur devis",
    status: "Roadmap",
  },
];

const faqs = [
  {
    question: "Puis-je changer de plan à tout moment ?",
    answer: "Oui, vous pouvez upgrader ou downgrader à tout moment. Les changements prennent effet immédiatement.",
  },
  {
    question: "Y a-t-il un engagement ?",
    answer: "Non, tous nos plans sont sans engagement. Vous pouvez annuler à tout moment.",
  },
  {
    question: "Comment fonctionne la facturation ?",
    answer: "La facturation est mensuelle. Vous recevez une facture au début de chaque période.",
  },
  {
    question: "Proposez-vous des réductions pour les comités étudiants ?",
    answer: "Oui ! Contactez-nous pour une offre spéciale comités et associations étudiantes.",
  },
];

export default function Pricing() {
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
                <span className="text-sm font-medium">Tarifs</span>
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Simple,<br />
                <span className="text-primary neon-text">transparent</span>
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground mb-8">
                Pas de frais cachés, pas de surprise. Choisissez le plan qui correspond à vos besoins.
              </p>
            </div>
          </div>
        </section>

        {/* Plans */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
              {plans.map((plan) => (
                <Card 
                  key={plan.name}
                  className={`relative bg-card border-border ${plan.popular ? 'border-primary/50 ring-2 ring-primary/20' : ''}`}
                >
                  {plan.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="px-4 py-1 rounded-full bg-primary text-primary-foreground text-sm font-medium">
                        Populaire
                      </span>
                    </div>
                  )}
                  <CardHeader className="text-center pb-4">
                    <div className={`w-14 h-14 rounded-2xl ${plan.popular ? 'bg-primary/20' : 'bg-muted'} flex items-center justify-center mx-auto mb-4`}>
                      <plan.icon className={plan.popular ? 'text-primary' : 'text-muted-foreground'} size={28} />
                    </div>
                    <h3 className="text-2xl font-bold">{plan.name}</h3>
                    <p className="text-muted-foreground text-sm">{plan.description}</p>
                    <div className="mt-4">
                      <span className="text-5xl font-black">{plan.price}</span>
                      <span className="text-muted-foreground">{plan.period}</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-3 mb-8">
                      {plan.features.map((feature) => (
                        <li key={feature.name} className="flex items-center gap-3">
                          {feature.included ? (
                            <Check className="text-green-500 shrink-0" size={18} />
                          ) : (
                            <X className="text-muted-foreground/50 shrink-0" size={18} />
                          )}
                          <span className={feature.included ? 'text-foreground' : 'text-muted-foreground/50'}>
                            {feature.name}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <Link to="/contact">
                      <Button 
                        className={`w-full ${plan.popular ? 'neon-glow-sm' : ''}`} 
                        variant={plan.ctaVariant}
                        size="lg"
                      >
                        {plan.cta}
                        <ArrowRight size={18} />
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Add-ons */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Add-ons <span className="text-primary">optionnels</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Ajoutez des fonctionnalités avancées selon vos besoins.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
              {addons.map((addon) => (
                <Card key={addon.name} className="bg-card border-border">
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <addon.icon className="text-primary" size={24} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-bold">{addon.name}</h3>
                          <span className="px-2 py-0.5 rounded-full bg-muted text-muted-foreground text-xs">
                            {addon.status}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">{addon.description}</p>
                        <span className="text-primary font-semibold">{addon.price}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Offre Comité */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <Card className="bg-gradient-to-br from-primary/10 to-transparent border-primary/30">
                <CardContent className="p-8 md:p-12">
                  <div className="flex flex-col md:flex-row items-center gap-8">
                    <div className="w-20 h-20 rounded-2xl bg-primary/20 flex items-center justify-center shrink-0">
                      <Users className="text-primary" size={40} />
                    </div>
                    <div className="flex-1 text-center md:text-left">
                      <h3 className="text-2xl font-bold mb-2">Offre Comités & Associations</h3>
                      <p className="text-muted-foreground mb-4">
                        Vous êtes un comité étudiant, une association ou un organisateur régulier ? 
                        Contactez-nous pour une offre sur mesure avec tarifs préférentiels.
                      </p>
                      <Link to="/contact">
                        <Button className="neon-glow-sm">
                          <MessageSquare size={18} />
                          Nous contacter
                        </Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Questions <span className="text-primary">fréquentes</span>
              </h2>
            </div>

            <div className="max-w-2xl mx-auto space-y-4">
              {faqs.map((faq) => (
                <div key={faq.question} className="p-6 rounded-xl bg-card border border-border">
                  <h3 className="font-bold mb-2">{faq.question}</h3>
                  <p className="text-muted-foreground text-sm">{faq.answer}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Prêt à <span className="text-primary">démarrer</span> ?
              </h2>
              <p className="text-muted-foreground mb-8">
                Commencez gratuitement et passez à Pro quand vous êtes prêt.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Commencer gratuitement
                    <ArrowRight size={18} />
                  </Button>
                </Link>
                <Link to="/contact">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    Demander une démo
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
