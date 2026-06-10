import 'package:flutter/material.dart';

import '../theme/tore_theme.dart';

class WalletTopButton extends StatelessWidget {
  const WalletTopButton({
    super.key,
    required this.onPressed,
    this.balance,
  });

  final VoidCallback onPressed;
  final double? balance;

  @override
  Widget build(BuildContext context) {
    final text = balance == null ? 'Wallet' : '€${balance!.toStringAsFixed(2)}';
    return FilledButton.tonalIcon(
      onPressed: onPressed,
      style: FilledButton.styleFrom(
        backgroundColor: ToreTokens.surface,
        foregroundColor: Colors.white,
        minimumSize: const Size(0, 40),
        padding: const EdgeInsets.symmetric(horizontal: ToreTokens.s12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      icon: const Icon(Icons.account_balance_wallet, size: 18),
      label: Text(
        text,
        style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
      ),
    );
  }
}
