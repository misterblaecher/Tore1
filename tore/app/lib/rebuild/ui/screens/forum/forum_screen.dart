import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';
import '../../widgets/section_header.dart';
import 'forum_cards.dart';

class ForumScreen extends StatefulWidget {
  const ForumScreen({
    super.key,
    required this.onOpenForum,
    required this.onSubmitRequest,
    this.fullPage = false,
  });

  final VoidCallback onOpenForum;
  final VoidCallback onSubmitRequest;
  final bool fullPage;

  @override
  State<ForumScreen> createState() => _ForumScreenState();
}

class _ForumScreenState extends State<ForumScreen> {
  late final TextEditingController _nameController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _eventNameController;
  late final TextEditingController _eventPlaceController;
  late final TextEditingController _eventDateController;

  String _spaceType = 'Comité';
  String _forumName = 'Comité Saint-Torè';
  String _forumDescription = 'Espace public · Liège · folklore étudiant';
  bool _spaceCreated = true;
  int _selectedPanel = 0;

  final List<ForumEventSummary> _events = [
    (
      title: 'Afond Night',
      detail: 'Live · 244 entrées · menu + bets + safe kit',
    ),
    (
      title: 'Saint-Torè warmup',
      detail: 'Vendredi 22:30 · QR join activé',
    ),
  ];

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: _forumName);
    _descriptionController = TextEditingController(
      text:
          'Accueil officiel du comité : description, bannière, événements, liens utiles et membres visibles.',
    );
    _eventNameController = TextEditingController(text: 'TD Outremeuse');
    _eventPlaceController =
        TextEditingController(text: 'Liège · salle à confirmer');
    _eventDateController = TextEditingController(text: 'Vendredi · 22:30');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _eventNameController.dispose();
    _eventPlaceController.dispose();
    _eventDateController.dispose();
    super.dispose();
  }

  void _submitRequest() {
    final name = _nameController.text.trim();
    setState(() {
      _spaceCreated = true;
      _forumName = name.isEmpty ? 'Nouveau $_spaceType TORÈ' : name;
      _forumDescription = '$_spaceType · demande acceptée · espace officiel';
      _selectedPanel = 1;
    });
    widget.onSubmitRequest();
    ToreFeedback.success(context, 'Espace créé : $_forumName');
  }

  void _createEvent() {
    final title = _eventNameController.text.trim();
    if (title.isEmpty) {
      ToreFeedback.error(context, 'Ajoute un nom d’événement.');
      return;
    }
    final place = _eventPlaceController.text.trim();
    final date = _eventDateController.text.trim();
    setState(() {
      _events.insert(0, (
        title: title,
        detail:
            '${date.isEmpty ? 'Date à confirmer' : date} · ${place.isEmpty ? 'Lieu à confirmer' : place} · brouillon TORÈ',
      ));
      _selectedPanel = 2;
    });
    ToreFeedback.success(context, 'Event créé dans le forum.');
  }

  @override
  Widget build(BuildContext context) {
    const panels = ['Créer', 'Gérer', 'Events', 'Salons'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(
          title: 'Forum TORÈ',
          actionLabel: widget.fullPage ? null : 'Page publique',
          onTap: widget.onOpenForum,
        ),
        Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: ToreTokens.border),
            color: ToreTokens.surface,
          ),
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: ToreTokens.rubyDeep,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: ToreTokens.yellowCta),
                      ),
                      child:
                          const Icon(Icons.forum, color: ToreTokens.yellowCta),
                    ),
                    const SizedBox(width: ToreTokens.s12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(_forumName,
                              style: Theme.of(context).textTheme.titleLarge),
                          Text(_forumDescription),
                        ],
                      ),
                    ),
                    ToreBadge(
                      label: _spaceCreated ? 'ACTIF' : 'BROUILLON',
                      color:
                          _spaceCreated ? ToreTokens.ruby : ToreTokens.border,
                    ),
                  ],
                ),
                const SizedBox(height: ToreTokens.s12),
                Text(
                  _descriptionController.text.trim().isEmpty
                      ? 'Page publique du forum : description, bannière, événements, liens utiles et membres publics.'
                      : _descriptionController.text.trim(),
                ),
                const SizedBox(height: ToreTokens.s12),
                Row(
                  children: [
                    Expanded(
                        child: ForumStat(
                            value: '${_events.length}', label: 'events')),
                    const SizedBox(width: ToreTokens.s8),
                    Expanded(
                        child: ForumStat(
                            value: _spaceCreated ? '18' : '0',
                            label: 'membres')),
                    const SizedBox(width: ToreTokens.s8),
                    Expanded(
                        child: ForumStat(
                            value: _spaceCreated ? '4' : '0', label: 'salons')),
                  ],
                ),
                const SizedBox(height: ToreTokens.s12),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: widget.onOpenForum,
                        icon: const Icon(Icons.open_in_new),
                        label: const Text('Page publique'),
                      ),
                    ),
                    const SizedBox(width: ToreTokens.s8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => setState(() => _selectedPanel = 1),
                        icon: const Icon(Icons.settings),
                        label: const Text('Gérer'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: ToreTokens.s12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (var i = 0; i < panels.length; i++) ...[
                ChoiceChip(
                  label: Text(panels[i]),
                  selected: _selectedPanel == i,
                  onSelected: (_) => setState(() => _selectedPanel = i),
                ),
                const SizedBox(width: ToreTokens.s8),
              ],
            ],
          ),
        ),
        const SizedBox(height: ToreTokens.s12),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 220),
          child: switch (_selectedPanel) {
            0 => ForumRequestCard(
                key: const ValueKey('create'),
                nameController: _nameController,
                descriptionController: _descriptionController,
                selectedType: _spaceType,
                onTypeChanged: (value) => setState(() => _spaceType = value),
                onSubmit: _submitRequest,
              ),
            1 => ForumAdminCard(
                key: const ValueKey('admin'),
                forumName: _forumName,
              ),
            2 => ForumEventsManagerCard(
                key: const ValueKey('events'),
                events: _events,
                eventNameController: _eventNameController,
                eventPlaceController: _eventPlaceController,
                eventDateController: _eventDateController,
                onCreateEvent: _createEvent,
              ),
            _ => const ForumPrivateChannelsCard(key: ValueKey('channels')),
          },
        ),
        const SizedBox(height: ToreTokens.s12),
        ForumFeedCard(events: _events),
        const SizedBox(height: ToreTokens.s12),
        const ForumStatsCard(),
      ],
    );
  }
}
