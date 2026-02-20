import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/app_context/app_context.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/utils/share_text.dart';
import '../../../core/network/network_state_provider.dart';
import '../../qr/presentation/code_entry_sheet.dart';
import '../../../state.dart';
import '../domain/event_public_view.dart';
import 'event_hub_screen.dart';

class EventPublicScreen extends ConsumerStatefulWidget {
  const EventPublicScreen({super.key, required this.eventId, this.autoJoin = false});

  final int eventId;
  final bool autoJoin;

  @override
  ConsumerState<EventPublicScreen> createState() => _EventPublicScreenState();
}

class _EventPublicScreenState extends ConsumerState<EventPublicScreen> {
  String _suffix(String code) {
    final clean = code.replaceAll(RegExp(r'[^A-Za-z0-9]'), '').toUpperCase();
    if (clean.isEmpty) return '—';
    return clean.length <= 6 ? clean : '…${clean.substring(clean.length - 6)}';
  }

  bool _loading = true;
  bool _joining = false;
  String? _error;
  EventPublicView? _event;

  String _idem() => 'join-public-${widget.eventId}-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final event = await ref.read(apiProvider).getEventPublic(widget.eventId);
      setState(() => _event = event);
      if (widget.autoJoin && event.canJoin) {
        await _join();
      }
    } catch (e) {
      setState(() => _error = 'Event privé / lien invalide');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<bool> _ensureCharterAcceptance({required int eventId, required String version}) async {
    final prefs = await SharedPreferences.getInstance();
    final key = 'charter_accepted_${eventId}_$version';
    if (prefs.getBool(key) == true) return true;
    final charter = await ref.read(apiProvider).eventCharter(eventId);
    if (!mounted) return false;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Charte de l’event'),
        content: SingleChildScrollView(child: Text((charter['text'] ?? '').toString())),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Refuser')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Accepter')),
        ],
      ),
    );
    if (accepted == true) {
      await prefs.setBool(key, true);
      return true;
    }
    return false;
  }

  Future<void> _join() async {
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    final runtimeBlocked = (_event?.canJoin == false);
    if (isWriteBlocked(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeBlocked: runtimeBlocked)) {
      setState(() => _error = writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeBlocked: runtimeBlocked));
      return;
    }
    setState(() {
      _joining = true;
      _error = null;
    });
    try {
      var payload = await ref.read(apiProvider).joinPublicEvent(eventId: widget.eventId, idempotencyKey: _idem());
      if (payload['charter_required'] == true) {
        final version = payload['charter_version']?.toString();
        if (version != null && await _ensureCharterAcceptance(eventId: widget.eventId, version: version)) {
          payload = await ref.read(apiProvider).joinPublicEvent(eventId: widget.eventId, idempotencyKey: _idem(), acceptedCharterVersion: version);
        } else {
          return;
        }
      }
      final eventPayload = Map<String, dynamic>.from(payload['event'] as Map);
      final modulesMapRaw = payload['modulesOn'];
      final modules = modulesMapRaw is Map
          ? Map<String, bool>.from(modulesMapRaw.map((k, v) => MapEntry(k.toString(), v == true)))
          : <String, bool>{for (final key in (_event?.modulesOn ?? const <String>[])) key: true};
      final eventName = (eventPayload['name'] ?? _event?.name ?? 'Event').toString();
      ref.read(appContextProvider.notifier).enterEvent(eventId: widget.eventId, eventName: eventName, activeEventModules: modules);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => EventHubScreen(eventId: widget.eventId, eventName: eventName)));
    } on DioException catch (e) {
      setState(() => _error = e.response?.data.toString() ?? 'Join impossible');
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }


  Future<void> _shareEventLink() async {
    final share = await ref.read(apiProvider).getEventShareV1(widget.eventId);
    String? shortUrl;
    if (ref.read(networkStatusProvider) == NetworkState.online) {
      try {
        final short = await ref.read(apiProvider).createShortlink(kind: 'event_share', eventId: widget.eventId, idempotencyKey: _idem());
        shortUrl = (short['shortUrl'] ?? '').toString();
      } catch (_) {}
    }
    final eventCode = (share['event_code'] ?? '').toString();
    final fallback = eventCode.length >= 4 ? eventCode.substring(eventCode.length - 4) : null;
    final url = pickShareUrl(shortUrl: shortUrl, webUrl: (share['webUrl'] ?? '').toString());
    await Share.share(shareText(url: url, fallbackSuffix: fallback), subject: _event?.name ?? 'Event TORÈ');
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (_error != null && _event == null) return Scaffold(appBar: AppBar(title: const Text('Event')), body: Center(child: Text(_error!)));
    final event = _event;
    if (event == null) return const SizedBox.shrink();
    return Scaffold(
      appBar: AppBar(title: const Text('Event public')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(event.name, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Host: ${event.hostName ?? '-'}'),
          Text('Lieu: ${event.venueName ?? '-'}'),
          Text('State: ${event.eventState}'),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, style: const TextStyle(color: Colors.redAccent))),
          const Spacer(),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _joining ? null : _join,
              child: Text(_joining ? 'Rejoindre…' : 'Rejoindre'),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _shareEventLink,
              icon: const Icon(Icons.share_outlined),
              label: const Text('Copier / Partager lien'),
            ),
          ),
          const SizedBox(height: 8),

          FutureBuilder<Map<String, dynamic>>(
            future: ref.read(apiProvider).getEventShareV1(widget.eventId),
            builder: (context, snap) {
              final code = (snap.data?['event_code'] ?? '').toString();
              return ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('Code (${_suffix(code)})'),
                subtitle: const Text('Fallback manuel si ouverture lien échoue'),
                trailing: IconButton(
                  onPressed: code.isEmpty ? null : () async {
                    await Clipboard.setData(ClipboardData(text: code));
                    if (!mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copié')));
                  },
                  icon: const Icon(Icons.copy_all_outlined),
                ),
              );
            },
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => showCodeEntrySheet(context),
              icon: const Icon(Icons.keyboard_alt_outlined),
              label: const Text('Entrer un code'),
            ),
          ),
        ]),
      ),
    );
  }
}
