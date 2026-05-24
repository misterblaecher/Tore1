import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class RunbookScreen extends StatelessWidget {
  const RunbookScreen({super.key, this.onOpenUrgency});
  final VoidCallback? onOpenUrgency;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Runbook',
        scopeBadges: const ['HELP', 'OPS'],
        body: ListView(
          shrinkWrap: true,
          children: [
            _SectionCard(
              title: 'Pre-Event Checklist',
              children: const [
                _Line('1. Vérifier réseau principal + hotspot secours.'),
                _Line(
                    '2. Imprimer QR JOIN / ENTRY / MENU et afficher en zone staff.'),
                _Line('3. Confirmer modules ON utiles, OFF restent cachés.'),
                _Line('4. Assigner au moins 2 agents entrée.'),
                _Line('5. Tester un scan QR valide + expiré.'),
                _Line('6. Vérifier presets de raison pour actions sensibles.'),
                _Line('7. Vérifier compteur d\'entrée à 0 avant ouverture.'),
                _Line(
                    '8. Brief équipe sur mode hors-ligne et fallback papier.'),
                _Line('9. Vérifier canal urgence / diffusion.'),
                _Line('10. Partager contacts support et procédure incident.'),
              ],
            ),
            const SizedBox(height: ToreTokens.s8),
            _SectionCard(
              title: 'Incident Quick Guide',
              children: [
                const _Line(
                    'Backend down: passer en mode lecture cache, geler écritures, informer équipes.'),
                const _Line(
                    'QR replay spikes: vérifier time skew, renforcer contrôle visuel, limiter accès temporairement.'),
                const _Line(
                    'Fraude suspectée: isoler ticket, escalader ORGA lead, journaliser faits horodatés.'),
                const _Line(
                    'Crowd issue: déclencher protocole sécurité et canal urgence immédiatement.'),
                const SizedBox(height: ToreTokens.s8),
                FilledButton.icon(
                    onPressed: onOpenUrgency,
                    icon: const Icon(Icons.warning_amber),
                    label: const Text('Ouvrir Urgency Actions')),
              ],
            ),
            const SizedBox(height: ToreTokens.s8),
            const _SectionCard(
              title: 'Support / FAQ',
              children: [
                _Line(
                    'QR inconnu: rescanner, vérifier source officielle, rediriger vers accueil si doute.'),
                _Line(
                    'QR expiré: demander régénération depuis écran ORGA exports.'),
                _Line(
                    'QR replay: bloquer validation immédiate et demander vérification identité/ticket.'),
                _Line(
                    'Toujours expliquer calmement l\'action suivante au participant.'),
              ],
            ),
          ],
        ),
      );
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s12),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s8),
            ...children
          ]),
        ),
      );
}

class _Line extends StatelessWidget {
  const _Line(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: ToreTokens.s8),
        child: Text(text),
      );
}
