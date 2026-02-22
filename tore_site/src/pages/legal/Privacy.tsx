import { Header, Footer } from "@/components/layout";
import { DISPLAY_PHONE_NUMBER, WHATSAPP_URL } from "@/lib/external-links";

export default function Privacy() {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="pt-24 pb-20">
        <section className="py-16 md:py-20 border-b border-border/50 section-ember-texture">
          <div className="container max-w-3xl space-y-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Confidentialité</p>
            <h1 className="text-3xl md:text-5xl font-semibold tracking-tight">Notice minimale — phase bêta TORÈ</h1>
            <div className="rounded-2xl border border-border/60 bg-card/40 p-6 md:p-8 metal-edge-card space-y-3 text-sm md:text-base text-muted-foreground leading-relaxed">
              <p>Nous collectons les données partagées volontairement pour la création de compte : nom, email, téléphone, statut WhatsApp, rôle et (si applicable) comité.</p>
              <p>Finalité : onboarding et qualification des demandes de compte TORÈ (ops/comité/bar), prise de contact et activation des accès.</p>
              <p>Base de traitement : consentement via l'envoi volontaire des formulaires externes.</p>
              <p>Conservation : 12 mois maximum après la demande, puis suppression ou anonymisation.</p>
              <p>Suppression : possible à tout moment, sur simple demande à l'équipe TORÈ.</p>
              <p>Partage : aucun usage commercial ; accès limité à l'équipe opérationnelle TORÈ.</p>
              <p>
                Contact confidentialité : <a href={WHATSAPP_URL} target="_blank" rel="noreferrer" className="text-accent hover:text-accent/90">WhatsApp</a> ({DISPLAY_PHONE_NUMBER}).
              </p>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
