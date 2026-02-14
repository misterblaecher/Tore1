import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/error_mapper.dart';
import '../../../state.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_chip.dart';
import '../../../ui/components/tore_cta.dart';

class OrderStatusLiveScreen extends ConsumerStatefulWidget {
  const OrderStatusLiveScreen({super.key, required this.orderId});

  final int orderId;

  @override
  ConsumerState<OrderStatusLiveScreen> createState() => _OrderStatusLiveScreenState();
}

class _OrderStatusLiveScreenState extends ConsumerState<OrderStatusLiveScreen> {
  Map<String, dynamic>? _order;
  String? _error;
  bool _loading = true;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
    _pollTimer = Timer.periodic(const Duration(seconds: 6), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final payload = await ref.read(apiProvider).getOrder(widget.orderId);
      if (!mounted) return;
      setState(() {
        _order = payload;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ErrorMapper.message(e);
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = (_order?['status'] ?? '').toString();
    final alias = _statusAlias(status);
    final expired = status.toUpperCase() == 'EXPIRED';

    return Scaffold(
      appBar: AppBar(title: const Text('Order Status Live')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ToreCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Commande #${widget.orderId}', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  ToreChip(label: alias, variant: _chipVariant(status)),
                  if (_order != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Text('Total: ${_order!['total_cents'] ?? 0} cents'),
                    ),
                ],
              ),
            ),
            if (_loading)
              const Expanded(child: Center(child: CircularProgressIndicator()))
            else if (_error != null)
              Expanded(
                child: Center(
                  child: Text('Erreur: $_error'),
                ),
              )
            else
              const Spacer(),
            if (expired)
              ToreCTA(
                label: 'Rafraîchir',
                onPressed: () => _load(),
              )
            else
              ToreCTA(
                label: 'Refresh',
                style: ToreCTAStyle.secondary,
                onPressed: () => _load(),
              ),
          ],
        ),
      ),
    );
  }

  String _statusAlias(String raw) {
    switch (raw.toUpperCase()) {
      case 'NEW':
        return 'pending';
      case 'IN_PROGRESS':
        return 'preparing';
      case 'READY':
        return 'ready';
      case 'SERVED':
        return 'claimed';
      case 'CANCELLED':
        return 'canceled';
      default:
        return raw.toLowerCase().isEmpty ? 'pending' : raw.toLowerCase();
    }
  }

  ToreChipVariant _chipVariant(String status) {
    switch (status.toUpperCase()) {
      case 'READY':
      case 'SERVED':
        return ToreChipVariant.ok;
      case 'CANCELLED':
        return ToreChipVariant.bad;
      case 'IN_PROGRESS':
        return ToreChipVariant.warn;
      default:
        return ToreChipVariant.info;
    }
  }
}
