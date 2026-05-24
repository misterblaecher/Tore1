import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/features/glossary/glossary_models.dart';
import 'package:tore/features/glossary/glossary_providers.dart';
import 'package:tore/shared/utils/write_gate.dart';
import 'package:tore/state.dart';
import 'package:tore/ui/components/components.dart';

final glossaryModuleProvider = FutureProvider<bool>((ref) async {
  final modules = await ref.read(apiProvider).modulesState();
  return modules['folklore_glossary'] == true;
});

class GlossaryHomeScreen extends ConsumerStatefulWidget {
  const GlossaryHomeScreen({super.key});

  @override
  ConsumerState<GlossaryHomeScreen> createState() => _GlossaryHomeScreenState();
}

class _GlossaryHomeScreenState extends ConsumerState<GlossaryHomeScreen> {
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final moduleOn = ref.watch(glossaryModuleProvider);
    return moduleOn.when(
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (_, __) =>
          const Scaffold(body: Center(child: Text('Module indisponible'))),
      data: (enabled) {
        if (!enabled)
          return const Scaffold(
              body: Center(child: Text('Glossaire indisponible')));
        final committeesAsync = ref.watch(glossaryPublicCommitteesProvider);
        return Scaffold(
          appBar: AppBar(title: const Text('Glossaire folklore')),
          body: committeesAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Erreur: $e')),
            data: (data) {
              final items = data.data
                  .where((c) =>
                      c.name.toLowerCase().contains(_search.toLowerCase()))
                  .toList(growable: false);
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  TextField(
                      decoration: const InputDecoration(
                          labelText: 'Rechercher un comité'),
                      onChanged: (v) => setState(() => _search = v)),
                  const SizedBox(height: 8),
                  if (data.cacheStatus.isCached)
                    Text(
                        'Offline cache • Dernière sync: ${data.cacheStatus.lastSyncAt?.toLocal().toString() ?? '-'}',
                        style: const TextStyle(color: Colors.orange)),
                  for (final c in items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: ToreCard(
                        child: ToreListRow(
                          title: c.name,
                          subtitle: c.shortName ?? 'Comité',
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                  builder: (_) => GlossaryTermsScreen(
                                      committeeId: c.id,
                                      committeeName: c.name,
                                      isPublicScope: true))),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
        );
      },
    );
  }
}

class GlossaryTermsScreen extends ConsumerStatefulWidget {
  const GlossaryTermsScreen(
      {super.key,
      required this.committeeId,
      required this.committeeName,
      required this.isPublicScope});

  final int committeeId;
  final String committeeName;
  final bool isPublicScope;

  @override
  ConsumerState<GlossaryTermsScreen> createState() =>
      _GlossaryTermsScreenState();
}

class _GlossaryTermsScreenState extends ConsumerState<GlossaryTermsScreen> {
  String _query = '';
  final Set<String> _tags = <String>{};

  @override
  Widget build(BuildContext context) {
    final module = ref.watch(glossaryModuleProvider);
    final enabled = module.maybeWhen(data: (v) => v, orElse: () => false);
    if (!enabled) {
      return Scaffold(
          appBar: AppBar(title: Text(widget.committeeName)),
          body: const Center(child: Text('Glossaire indisponible')));
    }
    final filters = GlossaryFilters(
        query: _query.isEmpty ? null : _query,
        tags: _tags.toList(growable: false));
    final settingsAsync = widget.isPublicScope
        ? ref.watch(glossaryPublicSettingsProvider(widget.committeeId))
        : ref.watch(committeeGlossarySettingsProvider(widget.committeeId));
    final termsAsync = widget.isPublicScope
        ? ref.watch(glossaryPublicTermsProvider(
            (committeeId: widget.committeeId, filters: filters)))
        : ref.watch(committeeGlossaryTermsProvider(
            (committeeId: widget.committeeId, filters: filters)));

    return Scaffold(
      appBar: AppBar(title: Text(widget.committeeName)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
                decoration: const InputDecoration(
                    labelText: 'Recherche terme/définition'),
                onChanged: (v) => setState(() => _query = v)),
          ),
          settingsAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
            data: (settings) => SizedBox(
              height: 42,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  const SizedBox(width: 8),
                  for (final tag in settings.data.availableTags)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: FilterChip(
                        label: Text(tag),
                        selected: _tags.contains(tag),
                        onSelected: (selected) => setState(() {
                          if (selected) {
                            _tags.add(tag);
                          } else {
                            _tags.remove(tag);
                          }
                        }),
                      ),
                    ),
                ],
              ),
            ),
          ),
          Expanded(
            child: termsAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Erreur: $e')),
              data: (data) => ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  if (data.cacheStatus.isCached)
                    ToreCard(
                      child: Text(
                          'Offline cache • Dernière sync ${data.cacheStatus.lastSyncAt?.toLocal().toString() ?? '-'}'),
                    ),
                  for (final term in data.data.items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: ToreCard(
                        child: ToreListRow(
                          title: term.term,
                          subtitle: term.definition,
                          trailing: term.isOfficial
                              ? const ToreChip(
                                  label: 'Officiel',
                                  variant: ToreChipVariant.live)
                              : null,
                          onTap: () => showModalBottomSheet<void>(
                              context: context,
                              builder: (_) =>
                                  TermDetailBottomSheet(term: term)),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class TermDetailBottomSheet extends StatelessWidget {
  const TermDetailBottomSheet({super.key, required this.term});

  final GlossaryTerm term;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(term.term, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text(term.definition),
            if ((term.examples ?? '').isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Exemple: ${term.examples!}'),
            ],
            const SizedBox(height: 8),
            Wrap(spacing: 6, children: [
              for (final t in term.tags)
                ToreChip(label: t, variant: ToreChipVariant.info)
            ]),
            if (term.isOfficial)
              const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: ToreChip(
                      label: 'Officiel', variant: ToreChipVariant.live)),
            const SizedBox(height: 8),
            Text('Maj: ${term.updatedAt.toLocal()}',
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class CommitteeGlossaryAdminScreen extends ConsumerWidget {
  const CommitteeGlossaryAdminScreen(
      {super.key, required this.committeeId, required this.committeeName});
  final int committeeId;
  final String committeeName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final module = ref.watch(glossaryModuleProvider);
    final enabled = module.maybeWhen(data: (v) => v, orElse: () => false);
    if (!enabled) {
      return Scaffold(
          appBar: AppBar(title: Text('$committeeName · Gérer Glossaire')),
          body: const Center(child: Text('Glossaire indisponible')));
    }
    final settingsAsync =
        ref.watch(committeeGlossarySettingsProvider(committeeId));
    final termsAsync = ref.watch(committeeGlossaryTermsProvider(
        (committeeId: committeeId, filters: const GlossaryFilters())));
    final canWriteNow = canWrite(ref, intent: WriteIntent.critical);
    final reason = writeDisabledReason(ref, intent: WriteIntent.critical);

    return Scaffold(
      appBar: AppBar(title: Text('$committeeName · Gérer Glossaire')),
      floatingActionButton: SizedBox(
        width: 180,
        child: ToreCTA(
          label: 'Nouveau terme',
          onPressed: !canWriteNow
              ? null
              : () async {
                  final ok = await showModalBottomSheet<bool>(
                      context: context,
                      isScrollControlled: true,
                      builder: (_) =>
                          GlossaryTermEditorSheet(committeeId: committeeId));
                  if (ok == true)
                    invalidateGlossaryAfterWrite(ref, committeeId);
                },
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!canWriteNow && reason != null) ToreCard(child: Text(reason)),
          settingsAsync.when(
            loading: () => const CircularProgressIndicator(),
            error: (e, _) => Text('Erreur settings: $e'),
            data: (settings) => SwitchListTile(
              title: const Text('Glossaire public'),
              subtitle: const Text('Visible depuis l’espace public'),
              value: settings.data.publicEnabled,
              onChanged: !canWriteNow
                  ? null
                  : (v) async {
                      await ref.read(apiProvider).committeeSetGlossarySettings(
                          committeeId, v,
                          idempotencyKey:
                              'g-set-${DateTime.now().millisecondsSinceEpoch}');
                      invalidateGlossaryAfterWrite(ref, committeeId);
                    },
            ),
          ),
          const ToreDivider(),
          termsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text('Erreur termes: $e'),
            data: (terms) => Column(
              children: [
                for (final term in terms.data.items)
                  ToreCard(
                    child: Column(
                      children: [
                        ToreListRow(
                          title: '${term.term} (${term.status})',
                          subtitle: term.definition,
                          trailing: term.isOfficial
                              ? const ToreChip(
                                  label: 'Officiel',
                                  variant: ToreChipVariant.live)
                              : null,
                          onTap: () async {
                            final ok = await showModalBottomSheet<bool>(
                                context: context,
                                isScrollControlled: true,
                                builder: (_) => GlossaryTermEditorSheet(
                                    committeeId: committeeId, term: term));
                            if (ok == true)
                              invalidateGlossaryAfterWrite(ref, committeeId);
                          },
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton(
                              onPressed: !canWriteNow
                                  ? null
                                  : () async {
                                      await ref
                                          .read(apiProvider)
                                          .committeeArchiveGlossaryTerm(
                                              committeeId, term.id,
                                              idempotencyKey:
                                                  'g-arch-${DateTime.now().millisecondsSinceEpoch}');
                                      invalidateGlossaryAfterWrite(
                                          ref, committeeId);
                                    },
                              child: const Text('Archiver'),
                            ),
                            TextButton(
                              onPressed: !canWriteNow
                                  ? null
                                  : () async {
                                      final reasonCtrl =
                                          TextEditingController();
                                      final ok = await showDialog<bool>(
                                        context: context,
                                        builder: (_) => AlertDialog(
                                          title:
                                              const Text('Supprimer le terme'),
                                          content: TextField(
                                              controller: reasonCtrl,
                                              decoration: const InputDecoration(
                                                  labelText: 'Raison')),
                                          actions: [
                                            TextButton(
                                                onPressed: () => Navigator.pop(
                                                    context, false),
                                                child: const Text('Annuler')),
                                            FilledButton(
                                                onPressed: () => Navigator.pop(
                                                    context, true),
                                                child: const Text('Delete'))
                                          ],
                                        ),
                                      );
                                      if (ok == true) {
                                        await ref
                                            .read(apiProvider)
                                            .committeeDeleteGlossaryTerm(
                                                committeeId,
                                                term.id,
                                                reasonCtrl.text.trim(),
                                                idempotencyKey:
                                                    'g-del-${DateTime.now().millisecondsSinceEpoch}');
                                        invalidateGlossaryAfterWrite(
                                            ref, committeeId);
                                      }
                                    },
                              child: const Text('Delete'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class GlossaryTermEditorSheet extends ConsumerStatefulWidget {
  const GlossaryTermEditorSheet(
      {super.key, required this.committeeId, this.term});

  final int committeeId;
  final GlossaryTerm? term;

  @override
  ConsumerState<GlossaryTermEditorSheet> createState() =>
      _GlossaryTermEditorSheetState();
}

class _GlossaryTermEditorSheetState
    extends ConsumerState<GlossaryTermEditorSheet> {
  late final TextEditingController _termCtrl;
  late final TextEditingController _definitionCtrl;
  late final TextEditingController _examplesCtrl;
  late final TextEditingController _tagsCtrl;
  late final TextEditingController _yearCtrl;
  bool _isOfficial = false;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _termCtrl = TextEditingController(text: widget.term?.term ?? '');
    _definitionCtrl =
        TextEditingController(text: widget.term?.definition ?? '');
    _examplesCtrl = TextEditingController(text: widget.term?.examples ?? '');
    _tagsCtrl = TextEditingController(text: widget.term?.tags.join(','));
    _yearCtrl =
        TextEditingController(text: widget.term?.yearId?.toString() ?? '');
    _isOfficial = widget.term?.isOfficial ?? false;
  }

  @override
  Widget build(BuildContext context) {
    final canWriteNow = canWrite(ref, intent: WriteIntent.critical);
    final reason = writeDisabledReason(ref, intent: WriteIntent.critical);
    return Padding(
      padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.term == null ? 'Nouveau terme' : 'Éditer terme'),
            TextField(
                controller: _termCtrl,
                decoration: const InputDecoration(labelText: 'Terme *')),
            TextField(
                controller: _definitionCtrl,
                decoration: const InputDecoration(labelText: 'Définition *'),
                maxLines: 3),
            TextField(
                controller: _examplesCtrl,
                decoration: const InputDecoration(labelText: 'Exemples')),
            TextField(
                controller: _tagsCtrl,
                decoration: const InputDecoration(labelText: 'Tags (virgule)')),
            TextField(
                controller: _yearCtrl,
                decoration:
                    const InputDecoration(labelText: 'YearId (optionnel)'),
                keyboardType: TextInputType.number),
            SwitchListTile(
                value: _isOfficial,
                onChanged: (v) => setState(() => _isOfficial = v),
                title: const Text('Officiel')),
            if (!canWriteNow && reason != null)
              Text(reason, style: const TextStyle(color: Colors.orange)),
            if (_error != null)
              Text(_error!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 8),
            ToreCTA(
              label: _loading ? '...' : 'Save',
              onPressed: !canWriteNow || _loading
                  ? null
                  : () async {
                      if (_termCtrl.text.trim().isEmpty ||
                          _definitionCtrl.text.trim().isEmpty) {
                        setState(
                            () => _error = 'Terme et définition sont requis');
                        return;
                      }
                      setState(() {
                        _loading = true;
                        _error = null;
                      });
                      final payload = {
                        'term': _termCtrl.text.trim(),
                        'definition': _definitionCtrl.text.trim(),
                        'examples': _examplesCtrl.text.trim().isEmpty
                            ? null
                            : _examplesCtrl.text.trim(),
                        'tags': _tagsCtrl.text
                            .split(',')
                            .map((e) => e.trim())
                            .where((e) => e.isNotEmpty)
                            .toList(growable: false),
                        'isOfficial': _isOfficial,
                        'yearId': int.tryParse(_yearCtrl.text.trim()),
                      };
                      try {
                        if (widget.term == null) {
                          await ref.read(apiProvider).committeeCreateGlossaryTerm(
                              widget.committeeId, payload,
                              idempotencyKey:
                                  'g-create-${DateTime.now().millisecondsSinceEpoch}');
                        } else {
                          await ref.read(apiProvider).committeeUpdateGlossaryTerm(
                              widget.committeeId, widget.term!.id, payload,
                              idempotencyKey:
                                  'g-upd-${DateTime.now().millisecondsSinceEpoch}');
                        }
                        if (context.mounted) Navigator.of(context).pop(true);
                      } catch (e) {
                        setState(() => _error = e.toString());
                      } finally {
                        setState(() => _loading = false);
                      }
                    },
            ),
          ],
        ),
      ),
    );
  }
}
