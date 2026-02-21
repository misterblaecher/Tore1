import { Header, Footer } from "@/components/layout";
import { Shield, Mail } from "lucide-react";

export default function Privacy() {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="pt-24 pb-20">
        {/* Hero */}
        <section className="py-16 md:py-20 border-b border-border">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6">
                <Shield size={16} />
                Document légal
              </div>
              <h1 className="text-4xl md:text-5xl font-bold mb-6">
                Politique de confidentialité
              </h1>
              <p className="text-muted-foreground">
                Dernière mise à jour : Février 2025
              </p>
            </div>
          </div>
        </section>

        {/* Content */}
        <section className="py-12">
          <div className="container">
            <div className="max-w-3xl mx-auto prose prose-invert prose-headings:text-foreground prose-p:text-muted-foreground prose-li:text-muted-foreground prose-strong:text-foreground">
              
              <h2>1. Introduction</h2>
              <p>
                TORÈ ("nous", "notre", "nos") s'engage à protéger la vie privée des utilisateurs de notre application et de notre site web. Cette politique de confidentialité explique comment nous collectons, utilisons, partageons et protégeons vos informations personnelles.
              </p>

              <h2>2. Données collectées</h2>
              <p>Nous collectons les types de données suivants :</p>
              
              <h3>2.1 Données fournies directement</h3>
              <ul>
                <li>Informations de compte : nom, email, numéro de téléphone (optionnel)</li>
                <li>Informations d'établissement : nom, adresse, type d'activité</li>
                <li>Données de contact : messages envoyés via nos formulaires</li>
              </ul>

              <h3>2.2 Données collectées automatiquement</h3>
              <ul>
                <li>Données de navigation : pages visitées, durée de visite</li>
                <li>Données techniques : type d'appareil, système d'exploitation, navigateur</li>
                <li>Données de scan QR : horodatage, type de scan (anonymisé)</li>
              </ul>

              <h2>3. Utilisation des données</h2>
              <p>Nous utilisons vos données pour :</p>
              <ul>
                <li>Fournir et améliorer nos services</li>
                <li>Personnaliser votre expérience utilisateur</li>
                <li>Communiquer avec vous (support, mises à jour)</li>
                <li>Générer des statistiques anonymisées</li>
                <li>Assurer la sécurité de la plateforme</li>
              </ul>

              <h2>4. Base légale du traitement</h2>
              <p>Nous traitons vos données sur les bases légales suivantes :</p>
              <ul>
                <li><strong>Exécution du contrat</strong> : pour fournir nos services</li>
                <li><strong>Consentement</strong> : pour les communications marketing (optionnel)</li>
                <li><strong>Intérêt légitime</strong> : pour améliorer nos services et assurer la sécurité</li>
                <li><strong>Obligation légale</strong> : pour respecter nos obligations réglementaires</li>
              </ul>

              <h2>5. Partage des données</h2>
              <p>
                Nous ne vendons jamais vos données personnelles. Nous pouvons les partager avec :
              </p>
              <ul>
                <li>Nos sous-traitants techniques (hébergement, analytics) sous contrat de confidentialité</li>
                <li>Les autorités compétentes si requis par la loi</li>
                <li>En cas de fusion ou acquisition, avec le nouvel exploitant</li>
              </ul>

              <h2>6. Conservation des données</h2>
              <p>
                Nous conservons vos données uniquement le temps nécessaire aux finalités décrites :
              </p>
              <ul>
                <li>Données de compte : durée de la relation commerciale + 3 ans</li>
                <li>Données de facturation : 10 ans (obligation légale)</li>
                <li>Données de navigation : 13 mois maximum</li>
                <li>Logs de sécurité : 12 mois</li>
              </ul>

              <h2>7. Vos droits</h2>
              <p>Conformément au RGPD, vous disposez des droits suivants :</p>
              <ul>
                <li><strong>Accès</strong> : obtenir une copie de vos données</li>
                <li><strong>Rectification</strong> : corriger des données inexactes</li>
                <li><strong>Effacement</strong> : demander la suppression de vos données</li>
                <li><strong>Limitation</strong> : restreindre le traitement de vos données</li>
                <li><strong>Portabilité</strong> : recevoir vos données dans un format structuré</li>
                <li><strong>Opposition</strong> : vous opposer au traitement de vos données</li>
              </ul>
              <p>
                Pour exercer ces droits, contactez-nous à : <strong>privacy@tore.app</strong>
              </p>

              <h2>8. Sécurité</h2>
              <p>
                Nous mettons en œuvre des mesures techniques et organisationnelles appropriées pour protéger vos données :
              </p>
              <ul>
                <li>Chiffrement des données en transit (TLS) et au repos</li>
                <li>Contrôles d'accès stricts</li>
                <li>Audits de sécurité réguliers</li>
                <li>Formation du personnel</li>
              </ul>

              <h2>9. Cookies</h2>
              <p>
                Nous utilisons des cookies pour améliorer votre expérience. Consultez notre{" "}
                <a href="/legal/cookies" className="text-primary hover:underline">
                  politique de cookies
                </a>{" "}
                pour plus de détails.
              </p>

              <h2>10. Transferts internationaux</h2>
              <p>
                Vos données sont principalement hébergées dans l'Union Européenne. En cas de transfert hors UE, nous nous assurons que des garanties appropriées sont en place (clauses contractuelles types, décision d'adéquation).
              </p>

              <h2>11. Modifications</h2>
              <p>
                Nous pouvons modifier cette politique. Les modifications significatives seront notifiées par email ou via l'application.
              </p>

              <h2>12. Contact</h2>
              <p>
                Pour toute question concernant cette politique ou vos données personnelles :
              </p>
              <div className="not-prose bg-card border border-border rounded-xl p-6 mt-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Mail className="text-primary" size={20} />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">Délégué à la protection des données</p>
                    <a href="mailto:privacy@tore.app" className="text-primary hover:underline">
                      privacy@tore.app
                    </a>
                  </div>
                </div>
              </div>

              <p className="mt-8">
                Vous pouvez également introduire une réclamation auprès de la CNIL (cnil.fr) si vous estimez que vos droits ne sont pas respectés.
              </p>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
