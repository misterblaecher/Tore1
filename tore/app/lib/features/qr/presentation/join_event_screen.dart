import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/qr/qr_parser.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import '../../../state.dart';
import '../../events/presentation/event_hub_screen.dart';
import 'qr_scanner_screen.dart';

class JoinEventScreen extends ConsumerStatefulWidget {
  const JoinEventScreen({super.key, this.prefillEventId, this.prefillCode, this.autoJoinCode = false});

  final int? prefillEventId;
  final String? prefillCode;
  final bool autoJoinCode;

  @override
  ConsumerState<JoinEventScreen> createState() => _JoinEventScreenState();
}

class _JoinEventScreenState extends ConsumerState<JoinEventScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final TextEditingController _codeCtrl = TextEditingController();

  bool _loadingPreview = false;
  bool _joining = false;
  String? _error;
  Map<String, dynamic>? _resolved;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    if (widget.prefillEventId != null) {
      _resolveEventById(widget.prefillEventId!);
    }
    if ((widget.prefillCode ?? '').trim().isNotEmpty) {
      _tabs.index = 1;
      _codeCtrl.text = widget.prefillCode!.trim().toUpperCase();
      if (widget.autoJoinCode) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            _resolveByCode();
          }
        });
      }
    }
  }

  @override
  void dispose() {
    _tabs.dispose();
    _codeCtrl.dispose();
    super.dispose();
  }

  Future<void> _resolveEventById(int eventId) async {
    setState(() {
      _loadingPreview = true;
      _error = null;
    });
    try {
      final event = await ref.read(apiProvider).event(eventId);
      setState(() {
        _resolved = {
          'event': event,
          'flags': {
            'charterEnabled': (event['charter_enabled'] == true),
            'charterVersion': event['charter_version']?.toString(),
          },
        };
      });
    } catch (e) {
      setState(() => _error = _joinErrorMessage(e));
    } finally {
      if (mounted) setState(() => _loadingPreview = false);
    }
  }

  Future<void> _scanJoinQr() async {
    final raw = await Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)));
    if (!mounted || raw == null || raw.trim().isEmpty) return;

    final payload = ref.read(qrParserProvider).parse(raw);
    if (payload.type != QrType.joinEvent || payload.eventId == null) {
      setState(() => _error = 'QR join_event invalide.');
      return;
    }
    _tabs.animateTo(0);
    await _resolveEventById(payload.eventId!);
  }

  Future<void> _resolveByCode() async {
    final code = _codeCtrl.text.trim().toUpperCase();
    if (code.isEmpty) return;
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    if (readOnly || degradedBlocked) {
      setState(() => _error = writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked));
      return;
    }

    setState(() {
      _joining = true;
      _error = null;
    });
    try {
      final payload = await ref.read(apiProvider).joinEventByCode(
            code: code,
            idempotencyKey: 'join-by-code-$code-${DateTime.now().millisecondsSinceEpoch}',
          );
      final eventPayload = Map<String, dynamic>.from(payload['event'] as Map);
      final eventId = int.parse(eventPayload['id'].toString());
      final modules = Map<String, bool>.from(((payload['modulesOn'] as Map?) ?? const {}).map((k, v) => MapEntry(k.toString(), v == true)));
      final eventName = (eventPayload['name'] ?? 'Event #$eventId').toString();
      ref.read(appContextProvider.notifier).enterEvent(eventId: eventId, eventName: eventName, activeEventModules: modules);
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => EventHubScreen(eventId: eventId, eventName: eventName)),
        (route) => route.isFirst,
      );
    } on DioException catch (e) {
      final detail = e.response?.data;
      final detailMap = detail is Map ? Map<String, dynamic>.from(detail) : const <String, dynamic>{};
      final reason = (((detailMap['detail'] as Map?)?['reason'])?.toString());
      if (reason == 'charter_acceptance_required') {
        final eventId = int.tryParse((((detailMap['detail'] as Map?)?['event_id']) ?? '').toString());
        final version = (((detailMap['detail'] as Map?)?['charter_version'])?.toString());
        if (eventId != null && version != null) {
          final accepted = await _ensureCharterAcceptance(eventId: eventId, version: version);
          if (accepted) {
            final payload = await ref.read(apiProvider).joinEventByCode(
                  code: code,
                  idempotencyKey: 'join-by-code-$code-${DateTime.now().millisecondsSinceEpoch}',
                  acceptedCharterVersion: version,
                );
            final eventPayload = Map<String, dynamic>.from(payload['event'] as Map);
            final modules = Map<String, bool>.from(((payload['modulesOn'] as Map?) ?? const {}).map((k, v) => MapEntry(k.toString(), v == true)));
            final eventName = (eventPayload['name'] ?? 'Event #$eventId').toString();
            ref.read(appContextProvider.notifier).enterEvent(eventId: eventId, eventName: eventName, activeEventModules: modules);
            if (!mounted) return;
            Navigator.of(context).pushAndRemoveUntil(
              MaterialPageRoute(builder: (_) => EventHubScreen(eventId: eventId, eventName: eventName)),
              (route) => route.isFirst,
            );
            return;
          }
        }
      }
      setState(() => _error = _joinErrorMessage(e));
    } catch (e) {
      setState(() => _error = _joinErrorMessage(e));
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  Future<void> _joinResolved() async {
    if (_resolved == null) return;
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    if (readOnly || degradedBlocked) return;

    final event = Map<String, dynamic>.from(_resolved!['event'] as Map);
    final eventId = int.tryParse(event['id'].toString());
    if (eventId == null) return;
    final flags = Map<String, dynamic>.from((_resolved!['flags'] as Map?) ?? const {});
    final charterEnabled = flags['charterEnabled'] == true;
    final charterVersion = flags['charterVersion']?.toString();

    setState(() {
      _joining = true;
      _error = null;
    });
    try {
      String? acceptedVersion;
      if (charterEnabled && charterVersion != null) {
        final accepted = await _ensureCharterAcceptance(eventId: eventId, version: charterVersion);
        if (!accepted) {
          setState(() => _joining = false);
          return;
        }
        acceptedVersion = charterVersion;
      }
      final payload = await ref.read(apiProvider).joinEvent(
            eventId: eventId,
            idempotencyKey: 'join-$eventId-${DateTime.now().millisecondsSinceEpoch}',
            acceptedCharterVersion: acceptedVersion,
          );
      final eventPayload = Map<String, dynamic>.from(payload['event'] as Map);
      final modules = Map<String, bool>.from(((payload['modulesOn'] as Map?) ?? const {}).map((k, v) => MapEntry(k.toString(), v == true)));
      final eventName = (eventPayload['name'] ?? 'Event #$eventId').toString();
      ref.read(appContextProvider.notifier).enterEvent(eventId: eventId, eventName: eventName, activeEventModules: modules);
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => EventHubScreen(eventId: eventId, eventName: eventName)),
        (route) => route.isFirst,
      );
    } catch (e) {
      setState(() => _error = _joinErrorMessage(e));
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  Future<bool> _ensureCharterAcceptance({required int eventId, required String version}) async {
    final prefs = await SharedPreferences.getInstance();
    final key = 'charter_accepted_${eventId}_$version';
    if (prefs.getBool(key) == true) return true;

    final charter = await ref.read(apiProvider).eventCharter(eventId);
    if (!mounted) return false;
    final accepted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _CharterSheet(version: version, text: charter['text']?.toString() ?? ''),
    );
    if (accepted == true) {
      await prefs.setBool(key, true);
      return true;
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    final writesBlocked = isWriteBlocked(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeBlocked: false);

    final event = _resolved == null ? null : Map<String, dynamic>.from(_resolved!['event'] as Map);
    final eventName = event?['name']?.toString() ?? 'Event';

    return Scaffold(
      appBar: AppBar(title: const Text('Join event')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            if (writesBlocked)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: ServiceLimitedBanner(message: writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked)),
              ),
            TabBar(controller: _tabs, tabs: const [Tab(text: 'Scan QR'), Tab(text: 'Enter code')]),
            const SizedBox(height: 12),
            Expanded(
              child: TabBarView(
                controller: _tabs,
                children: [
                  Center(
                    child: FilledButton.icon(onPressed: _scanJoinQr, icon: const Icon(Icons.qr_code_scanner), label: const Text('Scanner un QR join_event')),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextField(controller: _codeCtrl, decoration: const InputDecoration(labelText: 'eventCode', hintText: 'Ex: JOIN66')),
                      const SizedBox(height: 10),
                      FilledButton(onPressed: _joining ? null : _resolveByCode, child: const Text('Join with code')),
                    ],
                  ),
                ],
              ),
            ),
            if (_loadingPreview || _joining) const Padding(padding: EdgeInsets.only(top: 8), child: CircularProgressIndicator()),
            if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, style: const TextStyle(color: Colors.red))),
            if (event != null) ...[
              const Divider(height: 24),
              Text(eventName, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text((event['venue'] ?? 'Lieu non précisé').toString()),
              Text('${event['starts_at'] ?? ''} → ${event['ends_at'] ?? ''}', style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 10),
              FilledButton(onPressed: writesBlocked || _joining ? null : _joinResolved, child: const Text('Join event')),
            ],
          ],
        ),
      ),
    );
  }
}

class _CharterSheet extends StatefulWidget {
  const _CharterSheet({required this.version, required this.text});

  final String version;
  final String text;

  @override
  State<_CharterSheet> createState() => _CharterSheetState();
}

class _CharterSheetState extends State<_CharterSheet> {
  bool _accepted = false;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: SizedBox(
          height: MediaQuery.of(context).size.height * 0.8,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Charte Liège (${widget.version})', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 12),
                Expanded(child: SingleChildScrollView(child: Text(widget.text.isEmpty ? 'Aucune charte fournie.' : widget.text))),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _accepted,
                  onChanged: (v) => setState(() => _accepted = v == true),
                  title: const Text('J’accepte la charte'),
                ),
                FilledButton(onPressed: _accepted ? () => Navigator.of(context).pop(true) : null, child: const Text('Continuer')),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _joinErrorMessage(Object error) {
  if (error is DioException) {
    final reason = error.response?.data is Map ? (error.response?.data['detail']?['reason']?.toString()) : null;
    switch (reason) {
      case 'invalid_code':
        return 'Code invalide.';
      case 'charter_acceptance_required':
        return 'Tu dois accepter la charte avant de rejoindre.';
      case 'closed':
      case 'frozen':
        return 'Join refusé: event fermé.';
      default:
        return 'Impossible de rejoindre cet event.';
    }
  }
  return 'Impossible de rejoindre cet event.';
}
