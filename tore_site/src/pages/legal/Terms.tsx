import { Header, Footer } from "@/components/layout";
import { FileText, Mail } from "lucide-react";

export default function Terms() {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="pt-24 pb-20">
        {/* Hero */}
        <section className="py-16 md:py-20 border-b border-border">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6">
                <FileText size={16} />
                Document légal
              </div>
              <h1 className="text-4xl md:text-5xl font-bold mb-6">
                Conditions générales d'utilisation
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
              
              <h2>1. Objet</h2>
              <p>
                Les présentes conditions générales d'utilisation (CGU) régissent l'accès et l'utilisation de la plateforme TORÈ, application et site web permettant la gestion d'établissements (bars, restaurants) et d'événements via QR codes.
              </p>

              <h2>2. Définitions</h2>
              <ul>
                <li><strong>Plateforme</strong> : l'application mobile TORÈ et le site web associé</li>
                <li><strong>Utilisateur</strong> : toute personne accédant à la Plateforme</li>
                <li><strong>Compte</strong> : espace personnel créé par un Utilisateur</li>
                <li><strong>Établissement</strong> : bar, restaurant, ou lieu utilisant TORÈ</li>
                <li><strong>Événement</strong> : soirée ou manifestation gérée via TORÈ</li>
              </ul>

              <h2>3. Acceptation des conditions</h2>
              <p>
                L'utilisation de la Plateforme implique l'acceptation pleine et entière des présentes CGU. Si vous n'acceptez pas ces conditions, vous ne devez pas utiliser nos services.
              </p>

              <h2>4. Inscription et compte</h2>
              <h3>4.1 Création de compte</h3>
              <p>
                L'accès à certaines fonctionnalités nécessite la création d'un compte. L'Utilisateur s'engage à fournir des informations exactes et à les maintenir à jour.
              </p>
              
              <h3>4.2 Sécurité du compte</h3>
              <p>
                L'Utilisateur est responsable de la confidentialité de ses identifiants et de toutes les actions effectuées depuis son compte. En cas de suspicion d'utilisation frauduleuse, il doit nous en informer immédiatement.
              </p>

              <h3>4.3 Rôles et permissions</h3>
              <p>
                Les comptes peuvent avoir différents rôles (Owner, Manager, Staff). Chaque rôle dispose de permissions spécifiques. Le titulaire du compte Owner est responsable de la gestion des accès.
              </p>

              <h2>5. Services proposés</h2>
              <p>TORÈ propose notamment :</p>
              <ul>
                <li>Génération et gestion de QR codes</li>
                <li>Création de menus numériques</li>
                <li>Gestion d'événements et de billetterie</li>
                <li>Comptage et statistiques de fréquentation</li>
                <li>Outils de gestion pour établissements</li>
              </ul>
              <p>
                Les fonctionnalités disponibles dépendent du plan souscrit (Free, Pro, Add-ons).
              </p>

              <h2>6. Obligations de l'utilisateur</h2>
              <p>L'Utilisateur s'engage à :</p>
              <ul>
                <li>Utiliser la Plateforme conformément à sa destination</li>
                <li>Ne pas porter atteinte aux droits de tiers</li>
                <li>Ne pas tenter de contourner les mesures de sécurité</li>
                <li>Respecter la réglementation applicable (notamment RGPD)</li>
                <li>Ne pas utiliser la Plateforme à des fins illicites</li>
              </ul>

              <h2>7. Propriété intellectuelle</h2>
              <p>
                La Plateforme, son contenu, sa structure et son design sont protégés par les droits de propriété intellectuelle. Toute reproduction, modification ou distribution non autorisée est interdite.
              </p>
              <p>
                L'Utilisateur conserve la propriété de ses contenus mais accorde à TORÈ une licence d'utilisation nécessaire au fonctionnement des services.
              </p>

              <h2>8. Données personnelles</h2>
              <p>
                Le traitement des données personnelles est régi par notre{" "}
                <a href="/legal/privacy" className="text-primary hover:underline">
                  politique de confidentialité
                </a>
                .
              </p>

              <h2>9. Responsabilité</h2>
              <h3>9.1 Limitation de responsabilité</h3>
              <p>
                TORÈ s'efforce d'assurer la disponibilité de la Plateforme mais ne garantit pas un fonctionnement ininterrompu. Nous ne sommes pas responsables des dommages indirects, pertes de données ou manque à gagner.
              </p>

              <h3>9.2 Force majeure</h3>
              <p>
                TORÈ ne peut être tenu responsable en cas de force majeure (catastrophe naturelle, panne généralisée, etc.).
              </p>

              <h2>10. Tarification</h2>
              <p>
                Les tarifs sont indiqués sur notre page{" "}
                <a href="/pricing" className="text-primary hover:underline">
                  Pricing
                </a>
                . TORÈ se réserve le droit de modifier ses tarifs avec un préavis de 30 jours pour les utilisateurs existants.
              </p>

              <h2>11. Résiliation</h2>
              <h3>11.1 Par l'Utilisateur</h3>
              <p>
                L'Utilisateur peut supprimer son compte à tout moment depuis les paramètres. Les données seront supprimées conformément à notre politique de confidentialité.
              </p>

              <h3>11.2 Par TORÈ</h3>
              <p>
                TORÈ peut suspendre ou résilier un compte en cas de violation des présentes CGU, après notification préalable sauf en cas d'urgence.
              </p>

              <h2>12. Modifications des CGU</h2>
              <p>
                TORÈ peut modifier les présentes CGU. Les modifications seront notifiées par email ou via l'application. L'utilisation continue de la Plateforme après notification vaut acceptation.
              </p>

              <h2>13. Droit applicable</h2>
              <p>
                Les présentes CGU sont régies par le droit français. En cas de litige, les parties s'engagent à rechercher une solution amiable avant toute action judiciaire. À défaut, les tribunaux français seront compétents.
              </p>

              <h2>14. Contact</h2>
              <p>
                Pour toute question concernant ces conditions :
              </p>
              <div className="not-prose bg-card border border-border rounded-xl p-6 mt-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Mail className="text-primary" size={20} />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">Support juridique</p>
                    <a href="mailto:legal@tore.app" className="text-primary hover:underline">
                      legal@tore.app
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
