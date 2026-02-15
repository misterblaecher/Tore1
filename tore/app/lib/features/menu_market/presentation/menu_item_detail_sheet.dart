import 'package:flutter/material.dart';

import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_cta.dart';
import 'menu_item_availability.dart';

class MenuItemDetailSheet extends StatefulWidget {
  const MenuItemDetailSheet({
    super.key,
    required this.item,
    required this.onAdd,
    required this.enabled,
  });

  final Map<String, dynamic> item;
  final void Function(int qty) onAdd;
  final bool enabled;

  @override
  State<MenuItemDetailSheet> createState() => _MenuItemDetailSheetState();
}

class _MenuItemDetailSheetState extends State<MenuItemDetailSheet> {
  int qty = 1;

  @override
  Widget build(BuildContext context) {
    final name = (widget.item['name'] ?? 'Article').toString();
    final desc = (widget.item['description'] ?? widget.item['type'] ?? '').toString();
    final imageUrl = widget.item['image_url']?.toString();
    final tickets = ((widget.item['ticket_cost'] as num?)?.toInt()) ?? 1;
    final lastPriceChange = widget.item['price_change_pct']?.toString();
    final stockState = menuItemStockState(widget.item);
    final isOut = stockState == MenuItemStockState.out;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ToreCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (imageUrl != null && imageUrl.isNotEmpty)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.network(
                        imageUrl,
                        height: 160,
                        width: double.infinity,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                      ),
                    ),
                  const SizedBox(height: 8),
                  Text(name, style: Theme.of(context).textTheme.titleLarge),
                  if (desc.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(desc),
                    ),
                  const SizedBox(height: 6),
                  Text('Prix: 🎟️ $tickets'),
                  if (lastPriceChange != null) Text('Dernière variation: $lastPriceChange'),
                  if (stockState == MenuItemStockState.out)
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Chip(label: Text('RUPTURE')),
                    )
                  else if (stockState == MenuItemStockState.low)
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Chip(label: Text('LOW')),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: qty <= 1 ? null : () => setState(() => qty -= 1),
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                Text('$qty', style: Theme.of(context).textTheme.headlineSmall),
                IconButton(
                  onPressed: qty >= 10 ? null : () => setState(() => qty += 1),
                  icon: const Icon(Icons.add_circle_outline),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ToreCTA(
              label: 'Add to cart',
              onPressed: (widget.enabled && !isOut)
                  ? () {
                      widget.onAdd(qty);
                      Navigator.of(context).pop();
                    }
                  : null,
            ),
          ],
        ),
      ),
    );
  }
}
