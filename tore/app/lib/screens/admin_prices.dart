import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state.dart';
import '../shared/widgets/app_background.dart';
import '../shared/widgets/trading_card.dart';
import '../shared/widgets/price_text.dart';
import '../theme/tore_button.dart';
import '../theme/tore_colors.dart';

class AdminPricesScreen extends ConsumerStatefulWidget {
  const AdminPricesScreen({
    super.key,
    required this.eventId,
    this.embedded = false, // ✅ IMPORTANT pour Organizer tabs
  });

  final int eventId;

  /// Quand true => ne crée pas de Scaffold/AppBar, juste le contenu.
  /// Quand false (par défaut) => écran standalone complet.
  final bool embedded;

  @override
  ConsumerState<AdminPricesScreen> createState() => _AdminPricesScreenState();
}

class _AdminPricesScreenState extends ConsumerState<AdminPricesScreen> {
  bool saving = false;

  // drinkId -> controller €
  final Map<int, TextEditingController> _controllers = {};
  // drinkId -> last loaded effective cents
  final Map<int, int> _original = {};

  Future<List<Map<String, dynamic>>> _load() async {
    final api = ref.read(apiProvider);
    final raw = await api.adminPrices(widget.eventId);

    final items = raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();

    for (final it in items) {
      final id = (it['drink_id'] as num).toInt();
      final effective = (it['effective_price_cents'] as num).toInt();

      _original[id] = effective;

      _controllers.putIfAbsent(id, () {
        return TextEditingController(
          text: (effective / 100).toStringAsFixed(2),
        );
      });

      // sync controller with server value
      _controllers[id]!.text = (effective / 100).toStringAsFixed(2);
    }

    return items;
  }

  int? _parseEurosToCents(String s) {
    final cleaned = s.replaceAll(',', '.').trim();
    if (cleaned.isEmpty) return null;
    final v = double.tryParse(cleaned);
    if (v == null) return null;
    if (v < 0) return null;
    return (v * 100).round();
  }

  Future<void> _save(List<Map<String, dynamic>> items) async {
    setState(() => saving = true);
    final api = ref.read(apiProvider);

    try {
      final changes = <Map<String, dynamic>>[];

      for (final it in items) {
        final id = (it['drink_id'] as num).toInt();
        final ctrl = _controllers[id]!;
        final cents = _parseEurosToCents(ctrl.text);

        if (cents == null) continue;

        final orig = _original[id] ?? cents;
        if (cents != orig) {
          changes.add({'drink_id': id, 'price_cents': cents});
        }
      }

      if (changes.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text("Aucun changement à enregistrer")),
          );
        }
        return;
      }

      await api.setEventPrices(eventId: widget.eventId, prices: changes);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("✅ Prix enregistrés (${changes.length})")),
        );
      }

      // force reload UI
      setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("Erreur: $e")));
      }
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  Widget _buildContent() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _load(),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return Center(child: Text('Erreur: ${snap.error}'));
        }

        final items = snap.data ?? const [];
        if (items.isEmpty) {
          return const Center(child: Text("Aucune boisson"));
        }

        return Column(
          children: [
            Expanded(
              child: ListView.separated(
                itemCount: items.length,
                separatorBuilder: (_, __) => const Divider(height: 1), // ✅ fix
                itemBuilder: (_, i) {
                  final it = items[i];

                  final drinkId = (it['drink_id'] as num).toInt();
                  final name = (it['name'] ?? '').toString();
                  final type = (it['type'] ?? '').toString();
                  final base = (it['base_price_cents'] as num).toInt();
                  final override = it['override_price_cents'];
                  final effective =
                      (it['effective_price_cents'] as num).toInt();

                  final baseE = (base / 100).toStringAsFixed(2);
                  final effE = (effective / 100).toStringAsFixed(2);

                  final ctrl = _controllers[drinkId]!;

                  return ListTile(
                    title: Text(name),
                    subtitle: Text(
                      '$type • base: $baseE €'
                      '${override == null ? "" : " • override actif"}'
                      ' • actuel: $effE €',
                    ),
                    trailing: SizedBox(
                      width: 120,
                      child: TextField(
                        controller: ctrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: '€',
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: saving ? null : () => _save(items),
                    icon: saving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save),
                    label: Text(
                      saving ? "Enregistrement..." : "Enregistrer les prix",
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    // ✅ Version “onglet” (pas de Scaffold)
    if (widget.embedded) {
      return _buildContent();
    }

    // ✅ Version “écran standalone” (avec background)
    return AppBackground(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text('Admin prix — Event #${widget.eventId}'),
          backgroundColor: Colors.transparent,
          elevation: 0,
        ),
        body: _buildContent(),
      ),
    );
  }
}
