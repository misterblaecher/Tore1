import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../state.dart';

class AdminTicketsScreen extends ConsumerStatefulWidget {
  const AdminTicketsScreen({super.key, required this.eventId});
  final int eventId;

  @override
  ConsumerState<AdminTicketsScreen> createState() => _AdminTicketsScreenState();
}

class _AdminTicketsScreenState extends ConsumerState<AdminTicketsScreen> {
  final _controller = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  int? _eurosToCents(String s) {
    final v = double.tryParse(s.replaceAll(',', '.'));
    if (v == null) return null;
    return (v * 100).round();
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.watch(apiProvider);

    return FutureBuilder<Map<String, dynamic>>(
      future: api.getEvent(widget.eventId),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return Center(child: Text('Erreur: ${snap.error}'));
        }

        final event = snap.data ?? {};
        final currentCents =
            (event['ticket_value_cents'] as num?)?.toInt() ?? 100;
        final currentEuros = (currentCents / 100).toStringAsFixed(2);

        // Pré-remplir une seule fois
        if (_controller.text.isEmpty) {
          _controller.text = currentEuros;
        }

        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Valeur d’1 ticket',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _controller,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: '€ (ex: 2.00)',
                  prefixText: '€ ',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  icon: _saving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.save),
                  label: Text(_saving ? 'Enregistrement…' : 'Enregistrer'),
                  onPressed: _saving
                      ? null
                      : () async {
                          final cents = _eurosToCents(_controller.text);
                          if (cents == null || cents <= 0) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Montant invalide')),
                            );
                            return;
                          }
                          setState(() => _saving = true);
                          try {
                            await api.setTicketValue(
                              eventId: widget.eventId,
                              ticketValueCents: cents,
                            );
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    '✅ Ticket = ${(cents / 100).toStringAsFixed(2)} €',
                                  ),
                                ),
                              );
                            }
                          } catch (e) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Erreur: $e')),
                              );
                            }
                          } finally {
                            if (mounted) setState(() => _saving = false);
                          }
                        },
                ),
              ),
              const SizedBox(height: 12),
              Text('Actuel: € $currentEuros'),
            ],
          ),
        );
      },
    );
  }
}
