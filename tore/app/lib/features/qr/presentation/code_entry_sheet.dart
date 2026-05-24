import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/auth/providers.dart';
import '../../../state.dart';
import '../../../shared/utils/share_text.dart';
import '../../../shared/utils/share_intent.dart';
import '../../../core/network/network_state_provider.dart';
import '../../auth/presentation/email_auth_screen.dart';
import '../../events/presentation/event_public_screen.dart';
import 'code_entry_detector.dart';
import 'qr_scanner_screen.dart';

Future<void> showCodeEntrySheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => const CodeEntrySheet(),
  );
}

bool previewNeedsLogin(Map<String, dynamic> preview, {required bool isAuthed}) {
  return (preview['actionHint'] ?? '') == 'LOGIN_REQUIRED' && !isAuthed;
}

String formatSuffix(String? code) {
  final raw =
      (code ?? '').replaceAll(RegExp(r'[^A-Za-z0-9]'), '').toUpperCase();
  if (raw.isEmpty) return '—';
  if (raw.length <= 6) return raw;
  return '…${raw.substring(raw.length - 6)}';
}

String previewCopyHint(Map<String, dynamic> preview) {
  return (preview['copyHint'] ?? 'Ouvre TORÈ → Entrer un code').toString();
}

int? previewPublicEventId(Map<String, dynamic> preview) {
  if ((preview['kind'] ?? '') != 'event_public') return null;
  final deep = (preview['deeplink'] ?? '').toString();
  return int.tryParse(Uri.tryParse(deep)?.queryParameters['id'] ?? '');
}

class CodeEntrySheet extends ConsumerStatefulWidget {
  const CodeEntrySheet({super.key});

  @override
  ConsumerState<CodeEntrySheet> createState() => _CodeEntrySheetState();
}

class _CodeEntrySheetState extends ConsumerState<CodeEntrySheet> {
  static const _historyKey = 'manual_code_history_suffix_v1';

  final TextEditingController _ctrl = TextEditingController();
  final CodeEntryDetector _detector = const CodeEntryDetector();
  String? _clipboardSuggestion;
  CodeEntryResolution? _resolved;
  String? _status;
  Map<String, dynamic>? _preview;
  bool _submitting = false;
  List<String> _history = const [];

  String _idem() =>
      'code-consume-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  void initState() {
    super.initState();
    _loadClipboardSuggestion();
    _loadHistory();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _loadHistory() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() => _history = prefs.getStringList(_historyKey) ?? const []);
  }

  Future<void> _pushHistory(String code) async {
    final suffix = code.length <= 4 ? code : code.substring(code.length - 4);
    final prefs = await SharedPreferences.getInstance();
    final next = [suffix, ..._history.where((e) => e != suffix)]
        .take(5)
        .toList(growable: false);
    await prefs.setStringList(_historyKey, next);
    if (mounted) setState(() => _history = next);
  }

  void _analyze() {
    _ctrl.text = normalizeManualCode(_ctrl.text);
    setState(() => _resolved = _detector.detect(_ctrl.text));
  }

  Future<void> _loadClipboardSuggestion() async {
    final data = await Clipboard.getData('text/plain');
    final normalized = normalizeManualCode(data?.text ?? '');
    if (!mounted || normalized.isEmpty) return;
    setState(() => _clipboardSuggestion = normalized);
  }

  Future<void> _pasteClipboard() async {
    final data = await Clipboard.getData('text/plain');
    final normalized = normalizeManualCode(data?.text ?? '');
    if (normalized.isEmpty) return;
    _ctrl.text = normalized;
    _analyze();
  }

  Future<void> _copyPreviewCode() async {
    final preview = _preview;
    if (preview == null) return;
    final builder = ShareIntentBuilder(ShareIntentInput(
      copyValue: (preview['copyValue'] ?? '').toString(),
      copyHint: previewCopyHint(preview),
    ));
    final message = await builder.copyCodeOrHint();
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _continue() async {
    final code = normalizeManualCode(_ctrl.text);
    if (code.isEmpty || _submitting) return;
    setState(() {
      _submitting = true;
      _status = 'pending';
    });
    final navigator = Navigator.of(context);
    try {
      var preview = await ref.read(apiProvider).previewManualCode(code);
      if (mounted) setState(() => _preview = preview);
      final auth = ref.read(authSessionProvider);
      if (previewNeedsLogin(preview, isAuthed: auth.isAuthed)) {
        if (!navigator.mounted) return;
        await navigator
            .push(MaterialPageRoute(builder: (_) => const EmailAuthScreen()));
        await ref.read(authSessionProvider.notifier).refreshSession();
        preview = await ref.read(apiProvider).previewManualCode(code);
        if (mounted) setState(() => _preview = preview);
      }

      final id = previewPublicEventId(preview);
      if (id != null) {
        if (navigator.mounted) {
          navigator.pop();
          navigator.push(MaterialPageRoute(
              builder: (_) => EventPublicScreen(eventId: id, autoJoin: true)));
          return;
        }
      }

      final consumed = await ref
          .read(apiProvider)
          .consumeManualCode(code: code, idempotencyKey: _idem());
      final status = (consumed['status'] ?? 'pending').toString();
      setState(() => _status = status);
      await _pushHistory(code);
    } catch (_) {
      setState(() => _status = 'pending');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _shareResolvedLink() async {
    final resolved = _resolved;
    if (resolved == null) return;
    String url = resolved.source?.toString() ?? '';
    if (resolved.kind == CodeEntryKind.event &&
        resolved.eventId != null &&
        ref.read(networkStatusProvider) == NetworkState.online) {
      try {
        final short = await ref.read(apiProvider).createShortlink(
              kind: 'event_share',
              eventId: resolved.eventId,
              idempotencyKey: _idem(),
            );
        url = pickShareUrl(
            shortUrl: (short['shortUrl'] ?? '').toString(), webUrl: url);
      } catch (_) {}
    }
    final builder = ShareIntentBuilder(
        ShareIntentInput(openUrl: url, copyHint: kShareFallbackHintOffline));
    if (builder.primaryShareUrl.isEmpty) return;
    await Share.share(builder.shareText, subject: 'Lien TORÈ');
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Entrer un code', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          TextField(
            controller: _ctrl,
            decoration:
                const InputDecoration(hintText: 'Code ou lien tore://open?...'),
            autofocus: true,
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              OutlinedButton.icon(
                  onPressed: _pasteClipboard,
                  icon: const Icon(Icons.content_paste_outlined),
                  label: const Text('Coller')),
              const Spacer(),
              FilledButton(onPressed: _analyze, child: const Text('Analyser')),
            ],
          ),
          if (_clipboardSuggestion != null) ...[
            const SizedBox(height: 8),
            TextButton.icon(
                onPressed: _pasteClipboard,
                icon: const Icon(Icons.auto_awesome),
                label: Text('Coller "$_clipboardSuggestion"')),
          ],
          if (_resolved?.isKnown == true && _resolved?.source != null) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
                onPressed: _shareResolvedLink,
                icon: const Icon(Icons.share_outlined),
                label: const Text('Partager ce lien')),
          ],
          if (_history.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: _history
                  .map((suffix) => ActionChip(
                      label: Text('••••$suffix'),
                      onPressed: () => _ctrl.text = suffix))
                  .toList(growable: false),
            ),
          ],
          const SizedBox(height: 4),
          OutlinedButton.icon(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const QrScannerScreen()));
            },
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Scanner un QR'),
          ),
          const SizedBox(height: 8),
          FilledButton(
              onPressed: _submitting ? null : _continue,
              child: Text(_submitting ? 'Traitement…' : 'Continuer')),
          if (_preview != null) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                    child: Text(
                        'Code: ${formatSuffix((_preview?['displaySuffix'] ?? _preview?['normalizedCode']).toString())}')),
                IconButton(
                    onPressed: _copyPreviewCode,
                    icon: const Icon(Icons.copy_all_outlined),
                    tooltip: 'Copier code'),
              ],
            ),
          ],
          if (_status != null) ...[
            const SizedBox(height: 8),
            Text('Statut: $_status'),
          ],
        ],
      ),
    );
  }
}
