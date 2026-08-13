import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

typedef ForumEventSummary = ({String title, String detail});

class ForumStat extends StatelessWidget {
  const ForumStat({super.key, required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(ToreTokens.s8),
      decoration: BoxDecoration(
        color: ToreTokens.black.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: ToreTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: ToreTypography.monoNumber(context, size: 18)),
          Text(label,
              style: const TextStyle(color: Colors.white54, fontSize: 11)),
        ],
      ),
    );
  }
}

class ForumFeedCard extends StatelessWidget {
  const ForumFeedCard({super.key, required this.events});

  final List<ForumEventSummary> events;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Fil public', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s8),
            const Text(
              'Comme une page communautaire : annonces, events, souvenirs et liens utiles.',
            ),
            const SizedBox(height: ToreTokens.s12),
            for (final event in events.take(3))
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.event, color: ToreTokens.yellowCta),
                title: Text(event.title),
                subtitle: Text(event.detail),
                trailing: const Icon(Icons.chevron_right),
              ),
            const ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.campaign, color: ToreTokens.yellowCta),
              title: Text('Annonce comité'),
              subtitle: Text('Les inscriptions staff sont ouvertes.'),
              trailing: Icon(Icons.chevron_right),
            ),
          ],
        ),
      ),
    );
  }
}

class ForumRequestCard extends StatelessWidget {
  const ForumRequestCard({
    super.key,
    required this.nameController,
    required this.descriptionController,
    required this.selectedType,
    required this.onTypeChanged,
    required this.onSubmit,
  });

  final TextEditingController nameController;
  final TextEditingController descriptionController;
  final String selectedType;
  final ValueChanged<String> onTypeChanged;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    const types = [
      'Comité',
      'Cercle',
      'Ordre',
      'Régionale',
      'Rivageoise',
      'Autre'
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Demander un espace',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s8),
            const Text(
              'Comité, ordre, régionale ou rivageoise : la demande est modérée avant création.',
            ),
            const SizedBox(height: ToreTokens.s12),
            FilledButton.icon(
              onPressed: onSubmit,
              icon: const Icon(Icons.add_circle),
              label: const Text('Créer l’espace'),
            ),
            const SizedBox(height: ToreTokens.s12),
            Wrap(
              spacing: ToreTokens.s8,
              runSpacing: ToreTokens.s8,
              children: [
                for (final type in types)
                  ChoiceChip(
                    label: Text(type),
                    selected: selectedType == type,
                    onSelected: (_) => onTypeChanged(type),
                  ),
              ],
            ),
            const SizedBox(height: ToreTokens.s12),
            TextField(
              controller: nameController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                labelText: 'Nom du $selectedType',
                prefixIcon: const Icon(Icons.badge),
              ),
            ),
            const SizedBox(height: ToreTokens.s12),
            TextField(
              controller: descriptionController,
              style: const TextStyle(color: Colors.white),
              minLines: 2,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Description / justification',
                prefixIcon: Icon(Icons.description),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ForumEventsManagerCard extends StatelessWidget {
  const ForumEventsManagerCard({
    super.key,
    required this.events,
    required this.eventNameController,
    required this.eventPlaceController,
    required this.eventDateController,
    required this.onCreateEvent,
  });

  final List<ForumEventSummary> events;
  final TextEditingController eventNameController;
  final TextEditingController eventPlaceController;
  final TextEditingController eventDateController;
  final VoidCallback onCreateEvent;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Créer un event TORÈ',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s8),
            const Text(
              'L’event est ajouté au forum, prêt pour QR join, menu, staff, bets et recap.',
            ),
            const SizedBox(height: ToreTokens.s12),
            FilledButton.icon(
              onPressed: onCreateEvent,
              icon: const Icon(Icons.add),
              label: const Text('Créer l’event'),
            ),
            const SizedBox(height: ToreTokens.s12),
            TextField(
              controller: eventNameController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Nom de l’event',
                prefixIcon: Icon(Icons.event),
              ),
            ),
            const SizedBox(height: ToreTokens.s8),
            TextField(
              controller: eventDateController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Date / heure',
                prefixIcon: Icon(Icons.schedule),
              ),
            ),
            const SizedBox(height: ToreTokens.s8),
            TextField(
              controller: eventPlaceController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Lieu',
                prefixIcon: Icon(Icons.place),
              ),
            ),
            const SizedBox(height: ToreTokens.s12),
            for (final event in events)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.local_activity,
                    color: ToreTokens.yellowCta),
                title: Text(event.title),
                subtitle: Text(event.detail),
                trailing: const ToreBadge(label: 'TORÈ'),
              ),
          ],
        ),
      ),
    );
  }
}

class ForumPrivateChannelsCard extends StatelessWidget {
  const ForumPrivateChannelsCard({super.key});

  @override
  Widget build(BuildContext context) {
    const channels = [
      ('# annonces', 'Lecture publique, écriture responsables'),
      ('# staff-event', 'Préparation, QR pack, rôles terrain'),
      ('# comité-privé', 'Discussion interne et passation'),
      ('# modération', 'Signalements, permissions, accès'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Salons privés',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s8),
            const Text(
              'Des groupes de discussion type Discord, reliés aux rôles TORÈ et aux events.',
            ),
            const SizedBox(height: ToreTokens.s12),
            for (final channel in channels)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.tag, color: ToreTokens.yellowCta),
                title: Text(channel.$1),
                subtitle: Text(channel.$2),
                trailing: const ToreBadge(label: 'PRIVÉ'),
              ),
          ],
        ),
      ),
    );
  }
}

class ForumAdminCard extends StatelessWidget {
  const ForumAdminCard({super.key, required this.forumName});

  final String forumName;

  @override
  Widget build(BuildContext context) {
    const rows = [
      ('Infos forum', 'Description, bannière, liens utiles'),
      ('Membres', 'Invitations, visibilité publique'),
      ('Fonctions & grades', 'Rôles, permissions, accès'),
      ('Accès', 'Lecture, écriture, modération'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Gestion responsable',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s4),
            Text(forumName, style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: ToreTokens.s8),
            for (final row in rows)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.admin_panel_settings,
                    color: ToreTokens.yellowCta),
                title: Text(row.$1),
                subtitle: Text(row.$2),
                trailing: const Icon(Icons.chevron_right),
              ),
          ],
        ),
      ),
    );
  }
}

class ForumStatsCard extends StatelessWidget {
  const ForumStatsCard({super.key});

  @override
  Widget build(BuildContext context) {
    const rows = [
      ('Afond Night', '244 entrées · menu + bets + safe kit'),
      ('Rooftop After', '128 entrées · tickets + hunts'),
      ('Saint-Torè warmup', 'Post-event exporté'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Statistiques TORÈ',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: ToreTokens.s8),
            const Text(
              'Résumé post-event, modules activés, tickets, ventes et participation aux bets/hunts/battles.',
            ),
            const SizedBox(height: ToreTokens.s12),
            for (final row in rows)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading:
                    const Icon(Icons.insights, color: ToreTokens.yellowCta),
                title: Text(row.$1),
                subtitle: Text(row.$2),
              ),
          ],
        ),
      ),
    );
  }
}

class ConnectedOnlyForumPrompt extends StatelessWidget {
  const ConnectedOnlyForumPrompt({super.key});

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.lock, color: ToreTokens.yellowCta),
            SizedBox(height: ToreTokens.s12),
            Text(
              'Forum disponible après connexion',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            SizedBox(height: ToreTokens.s8),
            Text(
              'Connecte-toi pour rejoindre un comité, demander un espace ou gérer les rôles folkloriques.',
            ),
          ],
        ),
      ),
    );
  }
}
