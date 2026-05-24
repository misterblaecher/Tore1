import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';
import 'orga_admin_helpers.dart';
import 'orga_admin_providers.dart';

class OrgaSettingsScreen extends ConsumerStatefulWidget {
  const OrgaSettingsScreen({super.key, required this.orgId});

  final int orgId;

  @override
  ConsumerState<OrgaSettingsScreen> createState() => _OrgaSettingsScreenState();
}

class _OrgaSettingsScreenState extends ConsumerState<OrgaSettingsScreen> {
  final _name = TextEditingController();
  final _city = TextEditingController();
  final _instagram = TextEditingController();
  final _description = TextEditingController();

  String _visibility = 'PUBLIC';
  String _joinMode = 'OPEN_MEMBERSHIP';

  String _idem() =>
      'orga-settings-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  void dispose() {
    _name.dispose();
    _city.dispose();
    _instagram.dispose();
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final detailAsync = ref.watch(orgaDetailProvider(widget.orgId));
    final api = ref.read(apiProvider);
    final canWriteNow = canWrite(ref, intent: WriteIntent.nonCritical);
    final reason = writeDisabledReason(ref, intent: WriteIntent.nonCritical);

    return Scaffold(
      appBar: AppBar(title: const Text('Paramètres orga')),
      body: detailAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) =>
            const Center(child: Text('Erreur chargement paramètres')),
        data: (orga) {
          _name.text =
              _name.text.isEmpty ? (orga['name'] ?? '').toString() : _name.text;
          _city.text =
              _city.text.isEmpty ? (orga['city'] ?? '').toString() : _city.text;
          _instagram.text = _instagram.text.isEmpty
              ? (orga['instagram_handle'] ?? '').toString()
              : _instagram.text;
          _description.text = _description.text.isEmpty
              ? (orga['description'] ?? '').toString()
              : _description.text;
          _visibility = _visibility == 'PUBLIC' &&
                  (orga['visibility'] ?? '').toString().isNotEmpty
              ? (orga['visibility'] ?? 'PUBLIC').toString()
              : _visibility;
          _joinMode = _joinMode == 'OPEN_MEMBERSHIP' &&
                  (orga['join_mode'] ?? '').toString().isNotEmpty
              ? (orga['join_mode'] ?? 'OPEN_MEMBERSHIP').toString()
              : _joinMode;

          final payload = buildOrgaSettingsPayload(
            initial: orga,
            name: _name.text,
            city: _city.text,
            instagram: _instagram.text,
            description: _description.text,
            visibility: _visibility,
            joinMode: _joinMode,
          );

          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              if (!canWriteNow && reason != null) Text(reason),
              TextField(
                  controller: _name,
                  decoration: const InputDecoration(labelText: 'Nom'),
                  onChanged: (_) => setState(() {})),
              TextField(
                  controller: _city,
                  decoration: const InputDecoration(labelText: 'Ville'),
                  onChanged: (_) => setState(() {})),
              TextField(
                  controller: _instagram,
                  decoration: const InputDecoration(labelText: 'Instagram'),
                  onChanged: (_) => setState(() {})),
              TextField(
                  controller: _description,
                  decoration: const InputDecoration(labelText: 'Description'),
                  maxLines: 3,
                  onChanged: (_) => setState(() {})),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'PUBLIC', label: Text('Public')),
                  ButtonSegment(value: 'PRIVATE', label: Text('Privé'))
                ],
                selected: {_visibility},
                onSelectionChanged: (v) =>
                    setState(() => _visibility = v.first),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _joinMode,
                items: const [
                  'FOLLOW_ONLY',
                  'OPEN_MEMBERSHIP',
                  'REQUEST_TO_JOIN'
                ]
                    .map((e) => DropdownMenuItem(
                        value: e, child: Text(joinModeLabel(e))))
                    .toList(),
                onChanged: (v) =>
                    setState(() => _joinMode = v ?? 'OPEN_MEMBERSHIP'),
                decoration: const InputDecoration(labelText: 'Mode d’adhésion'),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: canWriteNow && payload.isNotEmpty
                    ? () async {
                        await api.updateOrga(
                            orgId: widget.orgId,
                            payload: payload,
                            idempotencyKey: _idem());
                        ref.invalidate(orgaDetailProvider(widget.orgId));
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('Paramètres enregistrés')));
                      }
                    : null,
                child: const Text('Enregistrer'),
              ),
            ],
          );
        },
      ),
    );
  }
}
