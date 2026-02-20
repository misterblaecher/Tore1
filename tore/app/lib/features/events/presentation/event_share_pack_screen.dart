import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../state.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/utils/share_text.dart';
import '../../../core/network/network_state_provider.dart';

class EventSharePackScreen extends ConsumerStatefulWidget {
  const EventSharePackScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<EventSharePackScreen> createState() => _EventSharePackScreenState();
}

class _EventSharePackScreenState extends ConsumerState<EventSharePackScreen> {
  String _suffix(String code) {
    final clean = code.replaceAll(RegExp(r'[^A-Za-z0-9]'), '').toUpperCase();
    if (clean.isEmpty) return '—';
    return clean.length <= 6 ? clean : '…${clean.substring(clean.length - 6)}';
  }
  static const String _publicWebBaseUrl = 'https://app.tore.be';
  static const Duration _ttl = Duration(hours: 24);
  Map<String, dynamic>? _pack;
  bool _fromCache = false;

  String _idem(String action) => '$action-${widget.eventId}-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';
  String get _cacheKey => 'share_pack_${widget.eventId}';

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final pack = await ref.read(apiProvider).getEventSharePackV1(widget.eventId);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cacheKey, jsonEncode({'payload': pack, 'exp': DateTime.now().toUtc().add(_ttl).toIso8601String()}));
      if (mounted) setState(() { _pack = pack; _fromCache = false; });
    } catch (_) {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_cacheKey);
      if (raw != null) {
        final decoded = Map<String, dynamic>.from(jsonDecode(raw) as Map);
        final exp = DateTime.tryParse((decoded['exp'] ?? '').toString());
        final payload = decoded['payload'];
        if (exp != null && exp.isAfter(DateTime.now().toUtc()) && payload is Map) {
          if (mounted) setState(() { _pack = Map<String, dynamic>.from(payload); _fromCache = true; });
          return;
        }
      }
      rethrow;
    }
  }

  Future<void> _copy(String value, {String message = 'Copié'}) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _openPrintableVersion({required bool canManage}) async {
    final path = canManage ? '/orga/events/${widget.eventId}/share-pack/print' : '/share/event/${widget.eventId}/print';
    await launchUrl(Uri.parse('$_publicWebBaseUrl$path'), mode: LaunchMode.externalApplication);
  }

  Future<void> _sharePrintableLink({required bool canManage}) async {
    final path = canManage ? '/orga/events/${widget.eventId}/share-pack/print' : '/share/event/${widget.eventId}/print';
    String shortUrl = '';
    if (ref.read(networkStatusProvider) == NetworkState.online) {
      try {
        final short = await ref.read(apiProvider).createShortlink(kind: 'event_share', eventId: widget.eventId, idempotencyKey: _idem('short-share'));
        shortUrl = (short['shortUrl'] ?? '').toString();
      } catch (_) {}
    }
    final url = pickShareUrl(shortUrl: shortUrl, webUrl: '$_publicWebBaseUrl$path');
    await Share.share(shareText(url: url), subject: 'Print pack TORÈ #${widget.eventId}');
  }

  Future<void> _rotateStaffInvite(String role) async {
    if (!canWrite(ref, intent: WriteIntent.critical)) return;
    try {
      await ref.read(apiProvider).rotateStaffInviteV1(eventId: widget.eventId, role: role, idempotencyKey: _idem('rotate-$role'));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Invite $role régénérée')));
      await _refresh();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Échec régénération $role: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final pack = _pack;
    final links = Map<String, dynamic>.from((pack?['links'] as Map?) ?? const <String, dynamic>{});
    final staffInvites = ((links['staffInvites'] as List?) ?? const []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
    final canManage = links.containsKey('staffInvites');
    final qr = Map<String, dynamic>.from((pack?['qr'] as Map?) ?? const <String, dynamic>{});
    final printUrl = canManage ? '$_publicWebBaseUrl/orga/events/${widget.eventId}/share-pack/print' : '$_publicWebBaseUrl/share/event/${widget.eventId}/print';
    final backupPrintUrl = (links['staffBackupPrintUrl'] ?? '').toString();

    return Scaffold(
      appBar: AppBar(title: const Text('Share pack')),
      body: pack == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_fromCache) const Card(child: ListTile(leading: Icon(Icons.cloud_off), title: Text('CACHE / OFFLINE'), subtitle: Text('Affichage du dernier share pack sauvegardé (TTL 24h).'))),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Wrap(spacing: 8, runSpacing: 8, children: [
                      FilledButton.icon(onPressed: () => _openPrintableVersion(canManage: canManage), icon: const Icon(Icons.print), label: const Text('Version imprimable')),
                      OutlinedButton.icon(onPressed: () => _copy(printUrl, message: 'Lien print copié'), icon: const Icon(Icons.link), label: const Text('Copier lien print')),
                      OutlinedButton.icon(onPressed: () => _sharePrintableLink(canManage: canManage), icon: const Icon(Icons.share), label: const Text('Partager')),
                      if (canManage && backupPrintUrl.isNotEmpty)
                        OutlinedButton.icon(
                          onPressed: () => launchUrl(Uri.parse(backupPrintUrl), mode: LaunchMode.externalApplication),
                          icon: const Icon(Icons.security),
                          label: const Text('Backup codes (print)'),
                        ),
                    ]),
                  ),
                ),
                const SizedBox(height: 8),
                _LinkCard(title: 'Public link', link: links['publicShare'], onCopy: _copy, suffix: _suffix(((links['joinPublic'] as Map?)?['code'] ?? '').toString())),
                const SizedBox(height: 8),
                _LinkCard(title: 'Join link', link: links['joinPublic'], onCopy: _copy, suffix: _suffix(((links['joinPublic'] as Map?)?['code'] ?? '').toString()), codeValue: ((links['joinPublic'] as Map?)?['code'] ?? '').toString()),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('Staff invites', style: TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      for (final invite in staffInvites)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text('${invite['role']} · ${invite['code']}'),
                          subtitle: Text('Expire: ${invite['expiresAt'] ?? '-'} · ${invite['status'] ?? '-'}\nCode: ${_suffix((invite['code'] ?? '').toString())}'),
                          trailing: Wrap(spacing: 4, children: [
                            IconButton(onPressed: () => _copy((invite['webUrl'] ?? '').toString(), message: 'Lien staff copié'), icon: const Icon(Icons.copy), tooltip: 'Copier lien staff'),
                            IconButton(onPressed: () => _copy((invite['code'] ?? '').toString(), message: 'Code copié'), icon: const Icon(Icons.copy_all_outlined), tooltip: 'Copier code'),
                            if ((invite['role'] ?? '').toString().toUpperCase() == 'MANAGER' && canManage)
                              IconButton(onPressed: () => _rotateStaffInvite('MANAGER'), icon: const Icon(Icons.autorenew), tooltip: 'Régénérer invite staff'),
                          ]),
                        ),
                    ]),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('QR payloads', style: TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      for (final e in qr.entries)
                        ListTile(contentPadding: EdgeInsets.zero, title: Text(e.key), subtitle: Text(e.value.toString()), trailing: IconButton(onPressed: () => _copy(e.value.toString()), icon: const Icon(Icons.copy))),
                    ]),
                  ),
                ),
                const SizedBox(height: 8),
                Text(jsonEncode(pack), style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
    );
  }
}

class _LinkCard extends StatelessWidget {
  const _LinkCard({required this.title, required this.link, required this.onCopy, this.suffix = '—', this.codeValue});

  final String title;
  final dynamic link;
  final Future<void> Function(String, {String message}) onCopy;
  final String suffix;
  final String? codeValue;

  @override
  Widget build(BuildContext context) {
    final map = Map<String, dynamic>.from((link as Map?) ?? const <String, dynamic>{});
    final web = (map['webUrl'] ?? '').toString();
    final deep = (map['deeplink'] ?? '').toString();
    return Card(
      child: ListTile(
        title: Text(title),
        subtitle: Text('$web\n$deep\nCode: $suffix'),
        isThreeLine: true,
        trailing: Wrap(spacing: 4, children: [
          IconButton(onPressed: web.isEmpty ? null : () => onCopy(web), icon: const Icon(Icons.copy)),
          IconButton(onPressed: (codeValue == null || codeValue!.isEmpty) ? null : () => onCopy(codeValue!, message: 'Code copié'), icon: const Icon(Icons.copy_all_outlined)),
        ]),
      ),
    );
  }
}
