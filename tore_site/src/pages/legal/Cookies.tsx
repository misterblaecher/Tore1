import { Header, Footer } from "@/components/layout";
import { Cookie, Mail } from "lucide-react";

export default function Cookies() {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="pt-24 pb-20">
        {/* Hero */}
        <section className="py-16 md:py-20 border-b border-border">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6">
                <Cookie size={16} />
                Document légal
              </div>
              <h1 className="text-4xl md:text-5xl font-bold mb-6">
                Politique de cookies
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
              
              <h2>1. Qu'est-ce qu'un cookie ?</h2>
              <p>
                Un cookie est un petit fichier texte stocké sur votre appareil (ordinateur, smartphone, tablette) lorsque vous visitez un site web. Les cookies permettent au site de reconnaître votre appareil et de mémoriser certaines informations sur vos préférences ou actions passées.
              </p>

              <h2>2. Cookies utilisés par TORÈ</h2>
              <p>Nous utilisons différents types de cookies :</p>

              <h3>2.1 Cookies essentiels</h3>
              <p>
                Ces cookies sont nécessaires au fonctionnement du site. Ils vous permettent de naviguer et d'utiliser les fonctionnalités de base.
              </p>
              <div className="not-prose overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Nom</th>
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Finalité</th>
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Durée</th>
                    </tr>
                  </thead>
                  <tbody className="text-muted-foreground">
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">session_id</td>
                      <td className="py-3 px-4">Maintien de la session utilisateur</td>
                      <td className="py-3 px-4">Session</td>
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">csrf_token</td>
                      <td className="py-3 px-4">Protection contre les attaques CSRF</td>
                      <td className="py-3 px-4">Session</td>
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">auth_token</td>
                      <td className="py-3 px-4">Authentification</td>
                      <td className="py-3 px-4">7 jours</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h3>2.2 Cookies de performance</h3>
              <p>
                Ces cookies nous aident à comprendre comment les visiteurs interagissent avec notre site en collectant des informations de manière anonyme.
              </p>
              <div className="not-prose overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Nom</th>
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Finalité</th>
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Durée</th>
                    </tr>
                  </thead>
                  <tbody className="text-muted-foreground">
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">_ga</td>
                      <td className="py-3 px-4">Google Analytics - distinction des visiteurs</td>
                      <td className="py-3 px-4">2 ans</td>
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">_gid</td>
                      <td className="py-3 px-4">Google Analytics - distinction des visiteurs</td>
                      <td className="py-3 px-4">24 heures</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h3>2.3 Cookies de fonctionnalité</h3>
              <p>
                Ces cookies permettent au site de mémoriser vos choix (langue, région, préférences d'affichage) pour une expérience personnalisée.
              </p>
              <div className="not-prose overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Nom</th>
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Finalité</th>
                      <th className="text-left py-3 px-4 text-foreground font-semibold">Durée</th>
                    </tr>
                  </thead>
                  <tbody className="text-muted-foreground">
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">theme</td>
                      <td className="py-3 px-4">Préférence de thème (dark/light)</td>
                      <td className="py-3 px-4">1 an</td>
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">locale</td>
                      <td className="py-3 px-4">Préférence de langue</td>
                      <td className="py-3 px-4">1 an</td>
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-3 px-4">cookie_consent</td>
                      <td className="py-3 px-4">Mémorisation de vos choix de cookies</td>
                      <td className="py-3 px-4">1 an</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h2>3. Gestion des cookies</h2>
              <p>
                Vous pouvez gérer vos préférences de cookies de plusieurs façons :
              </p>

              <h3>3.1 Bannière de consentement</h3>
              <p>
                Lors de votre première visite, une bannière vous permet d'accepter ou de refuser les cookies non essentiels. Vous pouvez modifier vos choix à tout moment via le lien "Paramètres cookies" en bas de page.
              </p>

              <h3>3.2 Paramètres du navigateur</h3>
              <p>
                Vous pouvez également configurer votre navigateur pour bloquer ou supprimer les cookies. Voici les liens vers les instructions des principaux navigateurs :
              </p>
              <ul>
                <li>
                  <a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Google Chrome
                  </a>
                </li>
                <li>
                  <a href="https://support.mozilla.org/fr/kb/activer-desactiver-cookies" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Mozilla Firefox
                  </a>
                </li>
                <li>
                  <a href="https://support.apple.com/fr-fr/guide/safari/sfri11471/mac" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Safari
                  </a>
                </li>
                <li>
                  <a href="https://support.microsoft.com/fr-fr/microsoft-edge/supprimer-les-cookies-dans-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Microsoft Edge
                  </a>
                </li>
              </ul>

              <h2>4. Conséquences du refus</h2>
              <p>
                Si vous refusez les cookies essentiels, certaines fonctionnalités du site peuvent ne pas fonctionner correctement. Le refus des cookies de performance et de fonctionnalité n'affecte pas l'utilisation de base du site.
              </p>

              <h2>5. Cookies tiers</h2>
              <p>
                Certains cookies sont déposés par des services tiers (Google Analytics). Ces services ont leurs propres politiques de confidentialité que nous vous invitons à consulter :
              </p>
              <ul>
                <li>
                  <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Google Privacy Policy
                  </a>
                </li>
              </ul>

              <h2>6. Durée de conservation</h2>
              <p>
                Les cookies ont des durées de vie variables, indiquées dans les tableaux ci-dessus. Les cookies de session sont supprimés à la fermeture du navigateur. Les cookies persistants restent jusqu'à leur expiration ou suppression manuelle.
              </p>

              <h2>7. Mises à jour</h2>
              <p>
                Cette politique peut être mise à jour pour refléter les évolutions de nos pratiques ou de la réglementation. La date de dernière mise à jour est indiquée en haut de cette page.
              </p>

              <h2>8. Contact</h2>
              <p>
                Pour toute question sur notre utilisation des cookies :
              </p>
              <div className="not-prose bg-card border border-border rounded-xl p-6 mt-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Mail className="text-primary" size={20} />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">Protection des données</p>
                    <a href="mailto:privacy@tore.app" className="text-primary hover:underline">
                      privacy@tore.app
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
