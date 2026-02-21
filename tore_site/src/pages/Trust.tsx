import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { 
  ArrowRight, 
  Shield,
  Lock,
  FileCheck,
  Eye,
  Clock,
  AlertTriangle,
  ToggleRight,
  ScrollText,
  Fingerprint,
  Database,
  CheckCircle2,
  XCircle,
  Scale
} from "lucide-react";

const principles = [
  {
    icon: ScrollText,
    title: "Audit trail complet",
    description: "Chaque action est loggée dans un ledger append-only. Impossible de modifier l'historique.",
  },
  {
    icon: Eye,
    title: "Consentement visible",
    description: "L'utilisateur sait toujours ce qu'on collecte et pourquoi. Pas de dark patterns.",
  },
  {
    icon: ToggleRight,
    title: "Privacy toggles",
    description: "Contrôles granulaires pour chaque type de données. L'utilisateur reste maître.",
  },
  {
    icon: Clock,
    title: "Rétention minimale",
    description: "On ne garde que ce qui est nécessaire, pas plus longtemps que prévu.",
  },
  {
    icon: Lock,
    title: "Chiffrement bout-en-bout",
    description: "Données sensibles chiffrées au repos et en transit. Standards bancaires.",
  },
  {
    icon: Fingerprint,
    title: "Auth sécurisée",
    description: "2FA, sessions signées, révocation instantanée. Zéro compromis.",
  },
];

const qrSecurity = [
  {
    icon: Lock,
    title: "QR signés cryptographiquement",
    description: "Chaque QR sensible (staff, paiement) est signé. Impossible à falsifier.",
  },
  {
    icon: Clock,
    title: "Expiration automatique",
    description: "Les QR critiques expirent après utilisation ou après un délai défini.",
  },
  {
    icon: AlertTriangle,
    title: "Révocation instantanée",
    description: "Un clic suffit pour invalider un QR compromis. Effet immédiat.",
  },
];

const nopolice = [
  {
    icon: AlertTriangle,
    title: "Warnings, pas blocages",
    description: "On préfère alerter plutôt que bloquer. Vous restez aux commandes.",
    type: "do",
  },
  {
    icon: ToggleRight,
    title: "Modules désactivables",
    description: "Si une feature ne vous convient pas, désactivez-la. Simple.",
    type: "do",
  },
  {
    icon: Eye,
    title: "Transparence totale",
    description: "Vous voyez exactement ce que TORÈ fait avec vos données.",
    type: "do",
  },
  {
    icon: XCircle,
    title: "Pas de surveillance cachée",
    description: "On ne track pas ce qui ne nous regarde pas.",
    type: "dont",
  },
  {
    icon: XCircle,
    title: "Pas de revente de données",
    description: "Vos données restent vos données. Point final.",
    type: "dont",
  },
  {
    icon: XCircle,
    title: "Pas de manipulation",
    description: "Pas de dark patterns, pas de friction artificielle.",
    type: "dont",
  },
];

const moneyBoundaries = [
  {
    icon: Database,
    title: "Ledger financier dédié",
    description: "Toutes les transactions money dans un ledger séparé, auditable à tout moment.",
  },
  {
    icon: Shield,
    title: "Anti-fraude intégré",
    description: "Détection d'anomalies avant même l'activation des modules paiement.",
  },
  {
    icon: Scale,
    title: "Séparation des responsabilités",
    description: "Owner ≠ Comptable ≠ Staff. Chaque rôle a ses limites strictes.",
  },
];

const rgpdRights = [
  "Droit d'accès à vos données",
  "Droit de rectification",
  "Droit à l'effacement (« droit à l'oubli »)",
  "Droit à la portabilité",
  "Droit d'opposition",
  "Droit à la limitation du traitement",
];

export default function Trust() {
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
                <Shield className="text-primary" size={18} />
                <span className="text-sm font-medium">Sécurité & RGPD</span>
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Confiance,<br />
                <span className="text-primary neon-text">par design</span>
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground mb-8">
                La sécurité n'est pas une feature, c'est une fondation. 
                Voici comment TORÈ protège vos données et celles de vos clients.
              </p>
            </div>
          </div>
        </section>

        {/* Principes */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Nos <span className="text-primary">principes</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Les règles non négociables qui guident chaque décision technique.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
              {principles.map((principle) => (
                <Card key={principle.title} className="bg-card border-border hover:border-primary/50 transition-all">
                  <CardContent className="p-6">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                      <principle.icon className="text-primary" size={24} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{principle.title}</h3>
                    <p className="text-muted-foreground text-sm">{principle.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* QR Security */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  QR <span className="text-primary">sécurisés</span>
                </h2>
                <p className="text-muted-foreground mb-8">
                  Les QR sensibles (rôles staff, paiements) ne sont pas de simples liens. 
                  Ils sont signés, tracés et révocables.
                </p>
                <div className="space-y-4">
                  {qrSecurity.map((item) => (
                    <div key={item.title} className="flex gap-4 p-4 rounded-xl bg-card border border-border">
                      <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <item.icon className="text-primary" size={24} />
                      </div>
                      <div>
                        <h3 className="font-bold mb-1">{item.title}</h3>
                        <p className="text-sm text-muted-foreground">{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="relative">
                <div className="max-w-sm mx-auto bg-card rounded-3xl border border-border p-8 text-center">
                  <div className="w-32 h-32 mx-auto mb-6 bg-gradient-to-br from-primary/20 to-transparent rounded-2xl flex items-center justify-center">
                    <Lock className="text-primary w-16 h-16" />
                  </div>
                  <p className="text-lg font-bold mb-2">QR signé</p>
                  <p className="text-sm text-muted-foreground mb-4">
                    Signature cryptographique + expiration + audit trail
                  </p>
                  <div className="flex items-center justify-center gap-2 text-green-500 text-sm">
                    <CheckCircle2 size={16} />
                    <span>Vérifié et valide</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pas de police */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Philosophie <span className="text-primary">"Pas de police"</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                TORÈ n'est pas là pour vous surveiller. On est là pour vous aider.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
              {/* Ce qu'on fait */}
              <div>
                <h3 className="font-bold text-green-500 mb-4 flex items-center gap-2">
                  <CheckCircle2 size={20} />
                  Ce qu'on fait
                </h3>
                <div className="space-y-4">
                  {nopolice.filter(item => item.type === "do").map((item) => (
                    <div key={item.title} className="flex gap-3 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
                      <item.icon className="text-green-500 shrink-0" size={20} />
                      <div>
                        <h4 className="font-semibold text-sm">{item.title}</h4>
                        <p className="text-xs text-muted-foreground">{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Ce qu'on ne fait PAS */}
              <div>
                <h3 className="font-bold text-red-500 mb-4 flex items-center gap-2">
                  <XCircle size={20} />
                  Ce qu'on ne fait PAS
                </h3>
                <div className="space-y-4">
                  {nopolice.filter(item => item.type === "dont").map((item) => (
                    <div key={item.title} className="flex gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                      <item.icon className="text-red-500 shrink-0" size={20} />
                      <div>
                        <h4 className="font-semibold text-sm">{item.title}</h4>
                        <p className="text-xs text-muted-foreground">{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Money Boundaries */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 border border-yellow-500/20 mb-6">
                <AlertTriangle className="text-yellow-500" size={18} />
                <span className="text-sm font-medium text-yellow-500">Money boundaries</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Quand l'argent <span className="text-primary">entre en jeu</span>
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Les modules paiement arrivent plus tard. En attendant, on pose les fondations anti-fraude.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {moneyBoundaries.map((item) => (
                <Card key={item.title} className="bg-card border-border">
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-yellow-500/10 flex items-center justify-center mx-auto mb-4">
                      <item.icon className="text-yellow-500" size={28} />
                    </div>
                    <h3 className="text-lg font-bold mb-2">{item.title}</h3>
                    <p className="text-muted-foreground text-sm">{item.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* RGPD */}
        <section className="py-16 md:py-24 bg-surface/50">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <div className="text-center mb-12">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                  <FileCheck className="text-primary" size={18} />
                  <span className="text-sm font-medium">RGPD</span>
                </div>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Conformité <span className="text-primary">RGPD</span>
                </h2>
                <p className="text-muted-foreground">
                  TORÈ respecte le Règlement Général sur la Protection des Données. 
                  Vos droits sont garantis.
                </p>
              </div>

              <Card className="bg-card border-border">
                <CardContent className="p-8">
                  <h3 className="font-bold mb-6">Vos droits :</h3>
                  <div className="grid sm:grid-cols-2 gap-4">
                    {rgpdRights.map((right) => (
                      <div key={right} className="flex items-center gap-3">
                        <CheckCircle2 className="text-green-500 shrink-0" size={18} />
                        <span className="text-sm">{right}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-8 p-4 rounded-xl bg-primary/10 border border-primary/20">
                    <p className="text-sm text-muted-foreground">
                      Pour exercer vos droits, contactez notre DPO à{" "}
                      <a href="mailto:privacy@tore.app" className="text-primary hover:underline">
                        privacy@tore.app
                      </a>
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Des questions sur la <span className="text-primary">sécurité</span> ?
              </h2>
              <p className="text-muted-foreground mb-8">
                Notre équipe est disponible pour répondre à toutes vos interrogations.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link to="/contact">
                  <Button size="lg" className="neon-glow-sm w-full sm:w-auto">
                    Nous contacter
                    <ArrowRight size={18} />
                  </Button>
                </Link>
                <Link to="/legal/privacy">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    Politique de confidentialité
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
