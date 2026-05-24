import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/auth/auth_repository.dart';
import 'package:tore/core/network/api_client.dart';

import 'market_models.dart';
import 'market_providers.dart';

class MarketScreen extends ConsumerWidget {
  final int eventId;
  const MarketScreen({super.key, required this.eventId});

  String _eur(int cents) => "${(cents / 100).toStringAsFixed(2)} €";

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final menuAsync = ref.watch(marketMenuProvider(eventId));

    return Scaffold(
      appBar: AppBar(title: const Text('Polymarket')),
      body: menuAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Erreur: $e')),
        data: (items) {
          if (items.isEmpty) return const Center(child: Text('Menu vide'));
          return ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final d = items[i];
              return ListTile(
                title: Text(d.name),
                subtitle: Text(d.type),
                trailing: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(_eur(d.effectivePriceCents),
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    if (d.effectivePriceCents != d.basePriceCents)
                      Text(
                        _eur(d.basePriceCents),
                        style: const TextStyle(
                          decoration: TextDecoration.lineThrough,
                          fontSize: 12,
                        ),
                      ),
                  ],
                ),
                onTap: () => _buySheet(context, ref, d),
              );
            },
          );
        },
      ),
    );
  }

  Future<void> _buySheet(
      BuildContext context, WidgetRef ref, MarketDrink drink) async {
    int qty = 1;

    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: 16 + MediaQuery.of(ctx).viewInsets.bottom,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(drink.name,
                      style: const TextStyle(
                          fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text("Prix: ${_eur(drink.effectivePriceCents)}"),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton(
                        onPressed: qty > 1 ? () => setState(() => qty--) : null,
                        icon: const Icon(Icons.remove),
                      ),
                      Text('$qty',
                          style: const TextStyle(
                              fontSize: 18, fontWeight: FontWeight.w600)),
                      IconButton(
                        onPressed:
                            qty < 50 ? () => setState(() => qty++) : null,
                        icon: const Icon(Icons.add),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () => Navigator.pop(ctx, true),
                      child: Text(
                          "Acheter (${_eur(drink.effectivePriceCents * qty)})"),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    if (ok != true) return;

    // ✅ récupérer le user_id via /auth/me (ton token est déjà géré par interceptor)
    final authRepo = AuthRepository(ApiClient.create());
    final me = await authRepo.getMe();
    final userId = me.id; // adapte si ton AppUser utilise un autre champ

    final repo = ref.read(marketRepositoryProvider);
    await repo.createOrder(
      eventId: eventId,
      userId: userId,
      items: [OrderItemIn(drinkId: drink.drinkId, qty: qty)],
    );

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Commande envoyée ✅")),
      );
    }
  }
}
