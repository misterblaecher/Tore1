import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../../state.dart';
import '../../charts/chart_models.dart';
import '../../charts/chart_providers.dart';

class CheckinScreen extends ConsumerStatefulWidget {
  const CheckinScreen({super.key});

  @override
  ConsumerState<CheckinScreen> createState() => _CheckinScreenState();
}

class _CheckinScreenState extends ConsumerState<CheckinScreen> {
  int _tab = 0; // 0 scan, 1 manuel
  bool _staffMode = false;

  // Scan mode state
  final _qrCtrl = TextEditingController();
  _ParsedCheckin? _parsed;
  String? _lastSignature;
  DateTime? _lastScanAt;

  // Manual mode state
  MenuDrinkMeta? _selected;
  int _qty = 1;
  bool _submitting = false;

  @override
  void dispose() {
    _qrCtrl.dispose();
    super.dispose();
  }

  void _parseQr() {
    setState(() {
      _parsed = _ParsedCheckin.tryParse(_qrCtrl.text.trim());
    });
  }

  bool _isDoubleScan(_ParsedCheckin p) {
    final sig = '${p.eventId}:${p.drinkId}:${p.qty}:${_staffMode ? 1 : 0}';
    final now = DateTime.now();
    if (_lastSignature == sig && _lastScanAt != null) {
      final dt = now.difference(_lastScanAt!);
      if (dt.inSeconds < 10) return true;
    }
    _lastSignature = sig;
    _lastScanAt = now;
    return false;
  }

  Future<void> _submitCheckin({
    required int eventId,
    required int drinkId,
    required int qty,
  }) async {
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      final api = ref.read(apiProvider);
      final userId = ref.read(userIdProvider);

      if (userId == null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Auth en cours...')),
          );
        }
        return;
      }

      await api.createCheckin(
        eventId: eventId,
        userId: userId,
        drinkId: drinkId,
        qty: qty,
        staffMode: _staffMode,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('✅ Check-in validé (×$qty)')),
      );

      // Reset UI a bit
      if (_tab == 0) {
        setState(() => _parsed = null);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erreur: ${ErrorMapper.message(e)}')),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Ensure session is warm
    ref.watch(meProvider);

    final ctx = ref.watch(appContextProvider);
    final eventId = ctx.activeEventId;

    if (eventId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Check-in')),
        body: const Center(child: Text('Sélectionne un event pour faire un check-in.')),
      );
    }

    final drinksAsync = ref.watch(eventMenuDrinksProvider(eventId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Check-in'),
        actions: [
          Row(
            children: [
              const Text('Staff'),
              Switch(
                value: _staffMode,
                onChanged: (v) => setState(() => _staffMode = v),
              ),
              const SizedBox(width: 6),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 0, label: Text('Scan QR'), icon: Icon(Icons.qr_code_scanner_outlined)),
                ButtonSegment(value: 1, label: Text('Manuel'), icon: Icon(Icons.search_outlined)),
              ],
              selected: <int>{_tab},
              onSelectionChanged: (s) => setState(() => _tab = s.first),
            ),
          ),
          Expanded(
            child: _tab == 0
                ? _scanTab(eventId)
                : _manualTab(eventId, drinksAsync),
          ),
        ],
      ),
    );
  }

  Widget _scanTab(int activeEventId) {
    final parsed = _parsed;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(
          controller: _qrCtrl,
          decoration: const InputDecoration(
            labelText: 'Contenu QR',
            hintText: 'Colle ici la valeur du QR (URL / JSON / event:drink:qty)',
            border: OutlineInputBorder(),
          ),
          maxLines: 3,
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _submitting ? null : _parseQr,
                icon: const Icon(Icons.search),
                label: const Text('Analyser'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: (_submitting || parsed == null)
                    ? null
                    : () async {
                        final p = parsed;
                        if (p == null) return;

                        if (_isDoubleScan(p)) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Double scan détecté (10s)')),
                          );
                          return;
                        }

                        await _submitCheckin(eventId: p.eventId, drinkId: p.drinkId, qty: p.qty);
                      },
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Valider'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        if (parsed == null)
          const Text(
            '''Astuce : formats acceptés
- URL: ...?event_id=1&drink_id=2&qty=1
- JSON: {"event_id":1,"drink_id":2,"qty":1}
- Simple: 1:2:1''',
          )
        else
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Prévisualisation', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  Text('Event: #${parsed.eventId}'),
                  Text('Drink: #${parsed.drinkId}'),
                  Text('Qty: ${parsed.qty}'),
                  if (parsed.eventId != activeEventId)
                    const Padding(
                      padding: EdgeInsets.only(top: 10),
                      child: Text(
                        '⚠️ Le QR vise un autre event que l’event actif.',
                        style: TextStyle(color: Colors.orangeAccent),
                      ),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _manualTab(int eventId, AsyncValue<List<MenuDrinkMeta>> drinksAsync) {
    return drinksAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text(ErrorMapper.message(e))),
      data: (drinks) {
        if (drinks.isEmpty) {
          return const Center(child: Text('Menu vide'));
        }

        _selected ??= drinks.first;

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            DropdownButtonFormField<MenuDrinkMeta>(
              value: _selected,
              decoration: const InputDecoration(
                labelText: 'Boisson',
                border: OutlineInputBorder(),
              ),
              items: drinks
                  .map(
                    (d) => DropdownMenuItem(
                      value: d,
                      child: Text(d.name, overflow: TextOverflow.ellipsis),
                    ),
                  )
                  .toList(),
              onChanged: (v) => setState(() => _selected = v),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Text('Quantité', style: TextStyle(fontWeight: FontWeight.w600)),
                const Spacer(),
                IconButton(
                  onPressed: _qty <= 1 ? null : () => setState(() => _qty -= 1),
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                Text(_qty.toString(), style: Theme.of(context).textTheme.titleLarge),
                IconButton(
                  onPressed: _qty >= 10 ? null : () => setState(() => _qty += 1),
                  icon: const Icon(Icons.add_circle_outline),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: (_submitting || _selected == null)
                  ? null
                  : () => _submitCheckin(
                        eventId: eventId,
                        drinkId: _selected!.drinkId,
                        qty: _qty,
                      ),
              icon: const Icon(Icons.check),
              label: const Text('Confirmer'),
            ),
            const SizedBox(height: 10),
            const Text(
              'Le mode Staff ajoute un flag côté backend (si supporté) et empêche le double-scan rapide.',
              style: TextStyle(fontSize: 12),
            ),
          ],
        );
      },
    );
  }
}

class _ParsedCheckin {
  final int eventId;
  final int drinkId;
  final int qty;

  const _ParsedCheckin({required this.eventId, required this.drinkId, required this.qty});

  static _ParsedCheckin? tryParse(String raw) {
    if (raw.isEmpty) return null;

    // 1) Simple format: event:drink:qty
    final parts = raw.split(':');
    if (parts.length == 3) {
      final e = int.tryParse(parts[0]);
      final d = int.tryParse(parts[1]);
      final q = int.tryParse(parts[2]);
      if (e != null && d != null && q != null) {
        return _ParsedCheckin(eventId: e, drinkId: d, qty: q);
      }
    }

    // 2) URL with query params
    final uri = Uri.tryParse(raw);
    if (uri != null && uri.queryParameters.isNotEmpty) {
      final e = int.tryParse(uri.queryParameters['event_id'] ?? uri.queryParameters['eventId'] ?? '');
      final d = int.tryParse(uri.queryParameters['drink_id'] ?? uri.queryParameters['drinkId'] ?? '');
      final q = int.tryParse(uri.queryParameters['qty'] ?? uri.queryParameters['quantity'] ?? '1') ?? 1;
      if (e != null && d != null) {
        return _ParsedCheckin(eventId: e, drinkId: d, qty: q);
      }
    }

    // 3) Very small JSON (no full parser, just heuristics)
    final cleaned = raw.replaceAll(RegExp(r'\s+'), '');
    if (cleaned.startsWith('{') && cleaned.endsWith('}')) {
      int? findInt(String key) {
        final m = RegExp('"$key":(\\d+)').firstMatch(cleaned);
        if (m == null) return null;
        return int.tryParse(m.group(1)!);
      }

      final e = findInt('event_id') ?? findInt('eventId');
      final d = findInt('drink_id') ?? findInt('drinkId');
      final q = findInt('qty') ?? findInt('quantity') ?? 1;
      if (e != null && d != null) return _ParsedCheckin(eventId: e, drinkId: d, qty: q);
    }

    return null;
  }
}
