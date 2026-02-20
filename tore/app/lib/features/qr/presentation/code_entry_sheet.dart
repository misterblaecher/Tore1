import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../community/presentation/orga_invite_join_screen.dart';
import '../../events/presentation/event_public_screen.dart';
import '../../events/presentation/staff_backup_join_screen.dart';
import '../../events/presentation/staff_invite_join_screen.dart';
import 'code_entry_detector.dart';
import 'join_event_screen.dart';
import 'qr_scanner_screen.dart';

Future<void> showCodeEntrySheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => const CodeEntrySheet(),
  );
}

class CodeEntrySheet extends StatefulWidget {
  const CodeEntrySheet({super.key});

  @override
  State<CodeEntrySheet> createState() => _CodeEntrySheetState();
}

class _CodeEntrySheetState extends State<CodeEntrySheet> {
  final TextEditingController _ctrl = TextEditingController();
  final CodeEntryDetector _detector = const CodeEntryDetector();
  String? _clipboardSuggestion;
  CodeEntryResolution? _resolved;

  @override
  void initState() {
    super.initState();
    _loadClipboardSuggestion();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
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

  void _continue() {
    final resolved = _resolved;
    if (resolved == null || !resolved.isKnown) return;
    Navigator.of(context).pop();
    if (resolved.kind == CodeEntryKind.join) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => JoinEventScreen(prefillCode: resolved.code, autoJoinCode: true)));
      return;
    }
    if (resolved.kind == CodeEntryKind.event && resolved.eventId != null) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventPublicScreen(eventId: resolved.eventId!)));
      return;
    }
    if (resolved.kind == CodeEntryKind.staffInvite) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => StaffInviteJoinScreen(code: resolved.code ?? '')));
      return;
    }
    if (resolved.kind == CodeEntryKind.staffBackup) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => StaffBackupJoinScreen(prefillEventId: resolved.eventId, prefillCode: resolved.code)));
      return;
    }
    if (resolved.kind == CodeEntryKind.orgaInvite) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaInviteJoinScreen(code: resolved.code ?? '')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    final resolved = _resolved;
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
            decoration: const InputDecoration(hintText: 'Code ou lien tore://open?...'),
            autofocus: true,
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              OutlinedButton.icon(
                onPressed: _pasteClipboard,
                icon: const Icon(Icons.content_paste_outlined),
                label: const Text('Coller'),
              ),
              const Spacer(),
              FilledButton(onPressed: _analyze, child: const Text('Analyser')),
            ],
          ),
          if (_clipboardSuggestion != null) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: _pasteClipboard,
              icon: const Icon(Icons.auto_awesome),
              label: Text('Coller "$_clipboardSuggestion"'),
            ),
          ],
          const SizedBox(height: 4),
          OutlinedButton.icon(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QrScannerScreen()));
            },
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Scanner un QR'),
          ),
          if (resolved != null) ...[
            const SizedBox(height: 12),
            Text(
              resolved.isKnown ? 'Type détecté: ${resolved.kind.name}' : 'Type inconnu. Vérifie le code ou utilise un lien /open.',
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: resolved.isKnown ? _continue : null,
              child: const Text('Continuer'),
            ),
          ],
        ],
      ),
    );
  }
}
