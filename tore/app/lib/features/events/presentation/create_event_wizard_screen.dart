import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';
import '../../../ui/components/components.dart';
import '../domain/event_create_models.dart';
import 'event_hub_screen.dart';

(String hostType, String? hostId) resolveCreateEventHostPrefill({
  Map<String, dynamic>? prefillOrga,
  int? prefillHostOrgaId,
}) {
  final prefillId =
      prefillHostOrgaId?.toString() ?? prefillOrga?['id']?.toString();
  if (prefillId != null && prefillId.isNotEmpty) {
    return ('orga', prefillId);
  }
  return ('user', null);
}

class CreateEventWizardScreen extends ConsumerStatefulWidget {
  const CreateEventWizardScreen({
    super.key,
    this.prefillOrga,
    this.prefillHostOrgaId,
  });

  final Map<String, dynamic>? prefillOrga;
  final int? prefillHostOrgaId;

  @override
  ConsumerState<CreateEventWizardScreen> createState() =>
      _CreateEventWizardScreenState();
}

class _CreateEventWizardScreenState
    extends ConsumerState<CreateEventWizardScreen> {
  int _step = 0;
  bool _loading = false;
  bool _publishNow = true;
  String _hostType = 'user';
  String? _hostId;
  List<Map<String, dynamic>> _myOrgas = const [];
  final _name = TextEditingController();
  final _venueName = TextEditingController();
  final _venueAddress = TextEditingController();
  final _description = TextEditingController();
  final _price = TextEditingController();
  DateTime _start = DateTime.now().add(const Duration(hours: 2));
  DateTime _end = DateTime.now().add(const Duration(hours: 6));
  bool _isFree = true;
  String? _selectedPreset;
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
  String? _postCreateNotice;
  bool _shareLoading = false;

  String _idem(String prefix) =>
      '$prefix-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(10000)}';

  @override
  void initState() {
    super.initState();
    final prefill = resolveCreateEventHostPrefill(
      prefillOrga: widget.prefillOrga,
      prefillHostOrgaId: widget.prefillHostOrgaId,
    );
    _hostType = prefill.$1;
    _hostId = prefill.$2;
    _loadOrgas();
  }

  @override
  void dispose() {
    _name.dispose();
    _venueName.dispose();
    _venueAddress.dispose();
    _description.dispose();
    _price.dispose();
    super.dispose();
  }

  Future<void> _loadOrgas() async {
    List<Map<String, dynamic>> orgs;
    try {
      orgs = await ref.read(apiProvider).myOrgas();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Organisations indisponibles : ${ErrorMapper.message(error)}',
          ),
        ),
      );
      return;
    }
    if (!mounted) return;
    setState(() {
      _myOrgas = orgs;
    });
  }

  Future<void> _submit() async {
    final validation = _validationMessage();
    if (validation != null) {
      _showMessage(validation);
      return;
    }
    final blocked = !canWrite(ref, intent: WriteIntent.critical);
    if (blocked) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            writeDisabledReason(ref, intent: WriteIntent.critical) ??
                'Writes bloqués',
          ),
        ),
      );
      return;
    }
    setState(() => _loading = true);
    final api = ref.read(apiProvider);
    int? id;
    try {
      final created = await api.createEventV1(
        idempotencyKey: _idem('event-create'),
        payload: buildEventCreatePayload(
          name: _name.text,
          start: _start,
          end: _end,
          visibility: _visibility,
          hostType: _hostType,
          hostId: _hostId,
          venueName: _venueName.text,
          venueAddress: _venueAddress.text,
          modulesOn: _modulesOn,
          isFree: _isFree,
          price: _price.text,
          description: _description.text,
        ),
      );
      id = (created['event_id'] as num?)?.toInt();
      if (id == null) throw Exception('missing event id');
    } catch (e) {
      if (!mounted) return;
      _showMessage('Création impossible : ${ErrorMapper.message(e)}');
      if (mounted) setState(() => _loading = false);
      return;
    }

    String? notice;
    if (_publishNow) {
      try {
        await api.publishEventV1(
          eventId: id,
          idempotencyKey: _idem('event-publish'),
        );
      } catch (error) {
        notice = 'Event créé, publication à réessayer : ${ErrorMapper.message(error)}';
      }
    }

    Map<String, dynamic>? share;
    try {
      share = await api.getEventShareV1(id);
    } catch (_) {
      notice = [
        if (notice != null) notice,
        'QR pack indisponible : vous pourrez le réessayer depuis cet écran.',
      ].join(' ');
    }
    if (!mounted) return;
    setState(() {
      _eventId = id;
      _share = share;
      _postCreateNotice = notice;
      _step = 5;
    });
    if (notice != null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(notice)));
    }
    ref
        .read(appContextProvider.notifier)
        .enterEvent(eventId: id, eventName: _name.text.trim());
    if (mounted) setState(() => _loading = false);
  }

  String? _validationMessage() => validateEventCreate(
    name: _name.text,
    start: _start,
    end: _end,
    isFree: _isFree,
    price: _price.text,
    description: _description.text,
  );

  void _showMessage(String message) => ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text(message)));

  void _nextStep() {
    if (_step == 1) {
      final validation = _validationMessage();
      if (validation != null) {
        _showMessage(validation);
        return;
      }
    }
    setState(() => _step += 1);
  }

  Future<void> _pickDateTime({required bool isStart}) async {
    final initial = isStart ? _start : _end;
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 3650)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initial),
    );
    if (time == null || !mounted) return;
    final selected = DateTime(
      date.year,
      date.month,
      date.day,
      time.hour,
      time.minute,
    );
    setState(() {
      if (isStart) {
        _start = selected;
      } else {
        _end = selected;
      }
    });
  }

  String _dateLabel(DateTime date) {
    String two(int value) => value.toString().padLeft(2, '0');
    return '${two(date.day)}/${two(date.month)}/${date.year} à ${two(date.hour)}:${two(date.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Créer un event')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ToreChip(
            label: 'Étape ${(_step + 1).clamp(1, 6)}/6',
            variant: ToreChipVariant.live,
          ),
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
                Expanded(
                  child: ToreCTA(
                    label: 'Retour',
                    style: ToreCTAStyle.secondary,
                    onPressed: _step > 0
                        ? () => setState(() => _step -= 1)
                        : null,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ToreCTA(
                    label: _step == 4
                        ? (_loading ? 'Création...' : 'Créer & continuer')
                        : 'Suivant',
                    onPressed: _loading
                        ? null
                        : (_step == 4 ? _submit : _nextStep),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _stepHost() => ToreCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Créer pour', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        RadioGroup<String>(
          groupValue: _hostType == 'orga' ? 'orga:${_hostId ?? ''}' : _hostType,
          onChanged: (value) => setState(() {
            if (value == null || value == 'user') {
              _hostType = 'user';
              _hostId = null;
              return;
            }
            _hostType = 'orga';
            _hostId = value.substring('orga:'.length);
          }),
          child: Column(
            children: [
              const RadioListTile<String>(value: 'user', title: Text('Moi')),
              if (_myOrgas.isNotEmpty)
                ..._myOrgas.map(
                  (orga) => RadioListTile<String>(
                    value: 'orga:${orga['orga']?['id'] ?? ''}',
                    title: Text((orga['orga']?['name'] ?? 'Orga').toString()),
                    subtitle: Text('Rôle ${(orga['role'] ?? '').toString()}'),
                  ),
                ),
            ],
          ),
        ),
      ],
    ),
  );

  Widget _stepInfos() => ToreCard(
    child: Column(
      children: [
        TextField(
          controller: _name,
          decoration: const InputDecoration(labelText: 'Nom event'),
        ),
        TextField(
          controller: _venueName,
          decoration: const InputDecoration(labelText: 'Lieu'),
        ),
        TextField(
          controller: _venueAddress,
          decoration: const InputDecoration(labelText: 'Adresse'),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Début'),
          subtitle: Text(_dateLabel(_start)),
          trailing: const Icon(Icons.edit_calendar),
          onTap: () => _pickDateTime(isStart: true),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Fin'),
          subtitle: Text(_dateLabel(_end)),
          trailing: const Icon(Icons.edit_calendar),
          onTap: () => _pickDateTime(isStart: false),
        ),
        TextField(
          controller: _description,
          maxLength: 280,
          maxLines: 3,
          decoration: const InputDecoration(
            labelText: 'Description publique courte',
          ),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Entrée gratuite'),
          value: _isFree,
          onChanged: (value) => setState(() => _isFree = value),
        ),
        if (!_isFree)
          TextField(
            controller: _price,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Prix d’entrée (€)',
              hintText: 'Ex. 8,50',
            ),
          ),
      ],
    ),
  );

  Widget _stepVisibility() => ToreCard(
    child: RadioGroup<String>(
      groupValue: _visibility,
      onChanged: (value) => setState(() => _visibility = value ?? 'PUBLIC'),
      child: const Column(
        children: [
          RadioListTile<String>(value: 'PUBLIC', title: Text('Public')),
          RadioListTile<String>(
            value: 'PRIVATE',
            title: Text('Privé (lien + QR)'),
          ),
        ],
      ),
    ),
  );

  Widget _stepModules() => ToreCard(
    child: Column(
      children: [
        DropdownButtonFormField<String>(
          initialValue: _selectedPreset,
          decoration: const InputDecoration(labelText: 'Configuration rapide'),
          items: eventModulePresets.keys
              .map((name) => DropdownMenuItem(value: name, child: Text(name)))
              .toList(),
          onChanged: (name) {
            if (name == null) return;
            setState(() {
              _selectedPreset = name;
              _modulesOn.addAll(modulesForPreset(name));
            });
          },
        ),
        ..._modulesOn.keys
            .map(
              (k) => SwitchListTile(
                title: Text(eventModuleLabels[k] ?? k),
                value: _modulesOn[k] == true,
                onChanged: (v) => setState(() {
                  _modulesOn[k] = v;
                  _selectedPreset = null;
                }),
              ),
            ),
      ],
    ),
  );

  Widget _stepPublish() => ToreCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Résumé avant publication',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(_name.text.trim()),
        Text('${_dateLabel(_start)} → ${_dateLabel(_end)}'),
        Text(
          _hostType == 'orga'
              ? 'Organisation : ${_hostName()}'
              : 'Organisé par moi',
        ),
        Text(
          'Lieu : ${_venueName.text.trim().isEmpty ? 'Non renseigné' : _venueName.text.trim()}',
        ),
        Text('Visibilité : ${_visibility == 'PUBLIC' ? 'Public' : 'Privé'}'),
        Text('Entrée : ${_isFree ? 'Gratuite' : '${_price.text.trim()} €'}'),
        if (_description.text.trim().isNotEmpty) Text(_description.text.trim()),
        Text(
          'Modules : ${_modulesOn.entries.where((entry) => entry.value).map((entry) => eventModuleLabels[entry.key] ?? entry.key).join(', ')}',
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Publier maintenant'),
          value: _publishNow,
          onChanged: (v) => setState(() => _publishNow = v),
        ),
      ],
    ),
  );

  String _hostName() {
    for (final orga in _myOrgas) {
      if (orga['orga']?['id']?.toString() == _hostId) {
        return (orga['orga']?['name'] ?? 'Orga').toString();
      }
    }
    return (widget.prefillOrga?['name'] ?? 'Orga').toString();
  }

  Widget _stepSharePack() {
    final share = _share ?? const <String, dynamic>{};
    return ToreCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Share pack',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          if (_postCreateNotice != null)
            Text(
              _postCreateNotice!,
              style: const TextStyle(color: Colors.orange),
            ),
          SelectableText('Lien: ${share['https_link'] ?? ''}'),
          const SizedBox(height: 6),
          SelectableText('QR join payload: ${share['qr_payload_join'] ?? ''}'),
          const SizedBox(height: 6),
          SelectableText('Code event: ${share['event_code'] ?? ''}'),
          const SizedBox(height: 10),
          ToreCTA(
            label: 'Copier lien',
            onPressed: share['https_link'] == null || _shareLoading
                ? null
                : () async {
                    final link = (share['https_link'] ?? '').toString();
                    await Clipboard.setData(ClipboardData(text: link));
                    if (!mounted) return;
                    ScaffoldMessenger.of(
                      context,
                    ).showSnackBar(const SnackBar(content: Text('Lien copié')));
                  },
          ),
          if (_share == null) ...[
            const SizedBox(height: 8),
            ToreCTA(
              label: _shareLoading
                  ? 'QR pack en cours…'
                  : 'Réessayer le QR pack',
              style: ToreCTAStyle.secondary,
              onPressed: _shareLoading || _eventId == null
                  ? null
                  : () async {
                      setState(() => _shareLoading = true);
                      try {
                        final result = await ref
                            .read(apiProvider)
                            .getEventShareV1(_eventId!);
                        if (!mounted) return;
                        setState(() {
                          _share = result;
                          _postCreateNotice = null;
                        });
                      } catch (error) {
                        if (!mounted) return;
                        _showMessage(
                          'QR pack indisponible : ${ErrorMapper.message(error)}',
                        );
                      } finally {
                        if (mounted) setState(() => _shareLoading = false);
                      }
                    },
            ),
          ],
          const SizedBox(height: 8),
          ToreCTA(
            label: 'Inviter staff',
            style: ToreCTAStyle.secondary,
            onPressed: _eventId == null
                ? null
                : () async {
                    try {
                      final invite = await ref
                          .read(apiProvider)
                          .createStaffInviteCodeV1(
                            eventId: _eventId!,
                            idempotencyKey: _idem('staff-invite'),
                          );
                      if (!mounted) return;
                      _showMessage('Code staff ${invite['code']}');
                    } catch (error) {
                      if (!mounted) return;
                      _showMessage(
                        'Invitation impossible : ${ErrorMapper.message(error)}',
                      );
                    }
                  },
          ),
          const SizedBox(height: 8),
          ToreCTA(
            label: 'Ouvrir Event Hub',
            style: ToreCTAStyle.secondary,
            onPressed: _eventId == null
                ? null
                : () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => EventHubScreen(
                        eventId: _eventId!,
                        eventName: _name.text.trim(),
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}
