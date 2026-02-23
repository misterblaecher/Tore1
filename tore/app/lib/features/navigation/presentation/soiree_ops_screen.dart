import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../api.dart';
import '../../../core/qr/qr_parser.dart';
import '../../../state.dart';
import '../../../ui/app_design_system.dart';
import '../../community/community_models.dart';
import '../../qr/presentation/qr_scanner_screen.dart';

class SoireeOpsScreen extends ConsumerStatefulWidget {
  const SoireeOpsScreen({super.key, required this.organizerMode});
  final bool organizerMode;

  @override
  ConsumerState<SoireeOpsScreen> createState() => _SoireeOpsScreenState();
}

class _SoireeOpsScreenState extends ConsumerState<SoireeOpsScreen> {
  final _nameCtrl = TextEditingController();
  final _venueCtrl = TextEditingController();
  DateTime _date = DateTime.now().add(const Duration(hours: 2));
  bool _busy = false;
  String? _msg;
  List<Map<String, dynamic>> _history = const [];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList('team_scan_history_v1') ?? const [];
    if (!mounted) return;
    setState(() => _history = raw.map((e) => Map<String, dynamic>.from(jsonDecode(e) as Map)).toList());
  }

  Future<void> _pushHistory(Map<String, dynamic> row) async {
    final prefs = await SharedPreferences.getInstance();
    final next = [jsonEncode(row), ...(prefs.getStringList('team_scan_history_v1') ?? const <String>[])].take(20).toList();
    await prefs.setStringList('team_scan_history_v1', next);
    await _loadHistory();
  }

  Future<void> _createEvent() async {
    setState(() {
      _busy = true;
      _msg = null;
    });
    try {
      final created = await ref.read(apiProvider).createSimpleEvent(name: _nameCtrl.text.trim(), startsAt: _date, venue: _venueCtrl.text.trim());
      if (!mounted) return;
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => SoireeEventDetailScreen(eventId: created['id'] as int, name: created['name'].toString())));
    } catch (_) {
      setState(() => _msg = 'Création impossible. Vérifie le réseau.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _scanForCheckin() async {
    final raw = await Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)));
    if (raw == null || raw.trim().isEmpty) return;
    final id = _parseEventId(raw);
    if (id == null) {
      await _pushHistory({'event_id': '-', 'timestamp': DateTime.now().toIso8601String(), 'status': 'error', 'message': 'QR non reconnu'});
      setState(() => _msg = 'QR non reconnu. Format attendu: event_checkin:<id>.');
      return;
    }
    try {
      final res = await ref.read(apiProvider).teamEventCheckin(eventId: id);
      final ok = res['status'] == 'ok';
      final message = res['message']?.toString() ?? (ok ? 'Check-in validé' : 'Erreur');
      await _pushHistory({'event_id': '$id', 'timestamp': DateTime.now().toIso8601String(), 'status': ok ? 'ok' : 'error', 'message': message});
      setState(() => _msg = message);
    } on DioException catch (e) {
      final message = e.response == null ? 'Offline' : (e.response?.data is Map ? (e.response?.data['detail'] ?? 'Erreur API').toString() : 'Erreur API');
      await _pushHistory({'event_id': '$id', 'timestamp': DateTime.now().toIso8601String(), 'status': 'error', 'message': message});
      setState(() => _msg = message);
    }
  }

  int? _parseEventId(String raw) {
    final trimmed = raw.trim();
    if (trimmed.startsWith('event_checkin:')) return int.tryParse(trimmed.split(':').last);
    final payload = ref.read(qrParserProvider).parse(trimmed);
    return payload.eventId;
  }

  @override
  Widget build(BuildContext context) {
    final mineAsync = widget.organizerMode ? ref.watch(myEventsProvider) : null;
    return Scaffold(
      appBar: AppBar(title: Text(widget.organizerMode ? 'Ops organisateur' : 'Ops équipe')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          if (widget.organizerMode) ...[
            const SectionTitle('Créer un event'),
            AppCard(
              child: Column(children: [
                TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Nom')),
                const SizedBox(height: AppSpacing.sm),
                TextField(controller: _venueCtrl, decoration: const InputDecoration(labelText: 'Lieu')),
                const SizedBox(height: AppSpacing.sm),
                ListTile(title: const Text('Date/heure'), subtitle: Text(_date.toLocal().toString()), onTap: () async {
                  final date = await showDatePicker(context: context, initialDate: _date, firstDate: DateTime.now().subtract(const Duration(days: 1)), lastDate: DateTime(2035));
                  if (date == null) return;
                  final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(_date));
                  if (time == null) return;
                  setState(() => _date = DateTime(date.year, date.month, date.day, time.hour, time.minute));
                }),
                PrimaryButton(label: 'Créer un event', icon: Icons.add, loading: _busy, onPressed: _busy ? null : _createEvent),
              ]),
            ),
            const SizedBox(height: AppSpacing.md),
            const SectionTitle('Mes events'),
            mineAsync!.when(
              loading: () => const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator())),
              error: (_, __) => const AppCard(child: Text('Impossible de charger tes events.')),
              data: (items) => items.isEmpty
                  ? const AppCard(child: Text('Aucun event pour le moment.'))
                  : Column(children: [for (final e in items) AppCard(child: ListTile(title: Text(e.name), subtitle: Text(e.startAt.toIso8601String()), onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => SoireeEventDetailScreen(eventId: e.id, name: e.name)))))])
            ),
          ] else ...[
            const SectionTitle('Scanner check-in'),
            PrimaryButton(label: 'Scanner QR', icon: Icons.qr_code_scanner_outlined, onPressed: _scanForCheckin),
            const SizedBox(height: AppSpacing.md),
            const SectionTitle('Historique local (20)'),
            if (_history.isEmpty)
              const AppCard(child: Text('Aucun scan pour le moment.'))
            else
              ..._history.map((h) => AppCard(child: ListTile(title: Text('Event ${h['event_id']}'), subtitle: Text(h['message'].toString()), trailing: AppChip(label: h['status'].toString())))),
          ],
          if (_msg != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_msg!)),
        ],
      ),
    );
  }
}

class SoireeEventDetailScreen extends StatelessWidget {
  const SoireeEventDetailScreen({super.key, required this.eventId, required this.name});
  final int eventId;
  final String name;

  @override
  Widget build(BuildContext context) {
    final payload = 'event_checkin:$eventId';
    return Scaffold(
      appBar: AppBar(title: Text(name)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          const SectionTitle('Payload check-in'),
          AppCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SelectableText(payload),
              const SizedBox(height: AppSpacing.sm),
              SecondaryButton(label: 'Copier', icon: Icons.copy, onPressed: () async {
                await Clipboard.setData(ClipboardData(text: payload));
                if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payload copié')));
              }),
            ]),
          ),
        ],
      ),
    );
  }
}

final myEventsProvider = FutureProvider<List<MyEventSummary>>((ref) async {
  final payload = await ref.read(apiProvider).myEvents();
  final out = <MyEventSummary>[];
  for (final bucket in ['LIVE', 'TODAY', 'UPCOMING', 'PAST']) {
    out.addAll(payload.buckets[bucket] ?? const <MyEventSummary>[]);
  }
  return out;
});
