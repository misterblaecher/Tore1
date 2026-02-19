import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';
import '../../../ui/components/components.dart';
import 'event_hub_screen.dart';


(String hostType, String? hostId) resolveCreateEventHostPrefill({Map<String, dynamic>? prefillOrga, int? prefillHostOrgaId}) {
  final prefillId = prefillHostOrgaId?.toString() ?? prefillOrga?['id']?.toString();
  if (prefillId != null && prefillId.isNotEmpty) {
    return ('orga', prefillId);
  }
  return ('user', null);
}


class CreateEventWizardScreen extends ConsumerStatefulWidget {
  const CreateEventWizardScreen({super.key, this.prefillOrga, this.prefillHostOrgaId});

  final Map<String, dynamic>? prefillOrga;
  final int? prefillHostOrgaId;

  @override
  ConsumerState<CreateEventWizardScreen> createState() => _CreateEventWizardScreenState();
}

class _CreateEventWizardScreenState extends ConsumerState<CreateEventWizardScreen> {
  int _step = 0;
  bool _loading = false;
  bool _publishNow = true;
  String _hostType = 'user';
  String? _hostId;
  List<Map<String, dynamic>> _myOrgas = const [];
  final _name = TextEditingController();
  final _venueName = TextEditingController();
  final _venueAddress = TextEditingController();
  DateTime _start = DateTime.now().add(const Duration(hours: 2));
  DateTime _end = DateTime.now().add(const Duration(hours: 6));
  String _visibility = 'PUBLIC';
  final Map<String, bool> _modulesOn = {
    'entry': true,
    'bar': true,
    'ticker': true,
    'music': false,
    'hunt': false,
    'battles': false,
    'safety': false,
    'wifi': false,
    'map': false,
    'polymarket_event': false,
    'classement': false,
    'broadcast': false,
  };
  Map<String, dynamic>? _share;
  int? _eventId;

  String _idem(String prefix) => '$prefix-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(10000)}';

  @override
  void initState() {
    super.initState();
    _loadOrgas();
  }

  @override
  void dispose() {
    _name.dispose();
    _venueName.dispose();
    _venueAddress.dispose();
    super.dispose();
  }

  Future<void> _loadOrgas() async {
    final orgs = await ref.read(apiProvider).myOrgas();
    if (!mounted) return;
    setState(() {
      _myOrgas = orgs;
      final prefill = resolveCreateEventHostPrefill(prefillOrga: widget.prefillOrga, prefillHostOrgaId: widget.prefillHostOrgaId);
      _hostType = prefill.$1;
      _hostId = prefill.$2;
    });
  }

  Future<void> _submit() async {
    final blocked = !canWrite(ref, intent: WriteIntent.critical);
    if (blocked) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(writeDisabledReason(ref, intent: WriteIntent.critical) ?? 'Writes bloqués')));
      return;
    }
    setState(() => _loading = true);
    try {
      final api = ref.read(apiProvider);
      final created = await api.createEventV1(
        idempotencyKey: _idem('event-create'),
        payload: {
          'name': _name.text.trim(),
          'startAt': _start.toUtc().toIso8601String(),
          'endAt': _end.toUtc().toIso8601String(),
          'visibility': _visibility,
          'host_type': _hostType,
          if (_hostId != null) 'host_id': _hostId,
          'venue': {'name': _venueName.text.trim(), 'address': _venueAddress.text.trim()},
          'modulesOn': _modulesOn,
          'rulesFlags': {},
        },
      );
      final id = (created['event_id'] as num?)?.toInt();
      if (id == null) throw Exception('missing event id');
      if (_publishNow) {
        await api.publishEventV1(eventId: id, idempotencyKey: _idem('event-publish'));
      }
      final share = await api.getEventShareV1(id);
      if (!mounted) return;
      setState(() {
        _eventId = id;
        _share = share;
        _step = 5;
      });
      ref.read(appContextProvider.notifier).enterEvent(eventId: id, eventName: _name.text.trim());
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Création impossible: $e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Créer un event')), 
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ToreChip(label: 'Étape ${(_step + 1).clamp(1, 6)}/6', variant: ToreChipVariant.live),
          const SizedBox(height: 12),
          if (_step == 0) _stepHost(),
          if (_step == 1) _stepInfos(),
          if (_step == 2) _stepVisibility(),
          if (_step == 3) _stepModules(),
          if (_step == 4) _stepPublish(),
          if (_step == 5) _stepSharePack(),
          const SizedBox(height: 12),
          if (_step < 5)
            Row(
              children: [
                Expanded(child: ToreCTA(label: 'Retour', style: ToreCTAStyle.secondary, onPressed: _step > 0 ? () => setState(() => _step -= 1) : null)),
                const SizedBox(width: 8),
                Expanded(
                  child: ToreCTA(
                    label: _step == 4 ? (_loading ? 'Création...' : 'Créer & continuer') : 'Suivant',
                    onPressed: _loading ? null : (_step == 4 ? _submit : () => setState(() => _step += 1)),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _stepHost() => ToreCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Créer pour', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          RadioListTile<String>(value: 'user', groupValue: _hostType, onChanged: (v) => setState(() { _hostType = v ?? 'user'; _hostId = null; }), title: const Text('Moi')),
          if (_myOrgas.isNotEmpty)
            ..._myOrgas.map((orga) => RadioListTile<String>(
                  value: 'orga:${orga['orga']?['id'] ?? ''}',
                  groupValue: _hostType == 'orga' ? 'orga:${_hostId ?? ''}' : _hostType,
                  onChanged: (_) => setState(() { _hostType = 'orga'; _hostId = (orga['orga']?['id'] ?? '').toString(); }),
                  title: Text((orga['orga']?['name'] ?? 'Orga').toString()),
                  subtitle: Text('Rôle ${(orga['role'] ?? '').toString()}'),
                )),
        ]),
      );

  Widget _stepInfos() => ToreCard(
        child: Column(children: [
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom event')),
          TextField(controller: _venueName, decoration: const InputDecoration(labelText: 'Lieu')),
          TextField(controller: _venueAddress, decoration: const InputDecoration(labelText: 'Adresse')),
        ]),
      );

  Widget _stepVisibility() => ToreCard(
        child: Column(children: [
          RadioListTile<String>(value: 'PUBLIC', groupValue: _visibility, onChanged: (v) => setState(() => _visibility = v ?? 'PUBLIC'), title: const Text('Public')),
          RadioListTile<String>(value: 'PRIVATE', groupValue: _visibility, onChanged: (v) => setState(() => _visibility = v ?? 'PRIVATE'), title: const Text('Privé (lien + QR)')),
        ]),
      );

  Widget _stepModules() => ToreCard(
        child: Column(
          children: _modulesOn.keys
              .map((k) => SwitchListTile(
                    title: Text(k),
                    value: _modulesOn[k] == true,
                    onChanged: (v) => setState(() => _modulesOn[k] = v),
                  ))
              .toList(),
        ),
      );

  Widget _stepPublish() => ToreCard(
        child: SwitchListTile(
          title: const Text('Publier maintenant'),
          value: _publishNow,
          onChanged: (v) => setState(() => _publishNow = v),
        ),
      );

  Widget _stepSharePack() {
    final share = _share ?? const <String, dynamic>{};
    return ToreCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Share pack', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        SelectableText('Lien: ${share['https_link'] ?? ''}'),
        const SizedBox(height: 6),
        SelectableText('QR join payload: ${share['qr_payload_join'] ?? ''}'),
        const SizedBox(height: 6),
        SelectableText('Code event: ${share['event_code'] ?? ''}'),
        const SizedBox(height: 10),
        ToreCTA(
          label: 'Copier lien',
          onPressed: () async {
            final link = (share['https_link'] ?? '').toString();
            await Clipboard.setData(ClipboardData(text: link));
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Lien copié')));
          },
        ),
        const SizedBox(height: 8),
        ToreCTA(
          label: 'Inviter staff',
          style: ToreCTAStyle.secondary,
          onPressed: _eventId == null
              ? null
              : () async {
                  final invite = await ref.read(apiProvider).createStaffInviteCodeV1(eventId: _eventId!, idempotencyKey: _idem('staff-invite'));
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Code staff ${invite['code']}')));
                },
        ),
        const SizedBox(height: 8),
        ToreCTA(
          label: 'Ouvrir Event Hub',
          style: ToreCTAStyle.secondary,
          onPressed: _eventId == null
              ? null
              : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventHubScreen(eventId: _eventId!, eventName: _name.text.trim()))),
        ),
      ]),
    );
  }
}
