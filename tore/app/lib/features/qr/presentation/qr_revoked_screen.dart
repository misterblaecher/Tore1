import 'package:flutter/material.dart';

import 'qr_status_screen.dart';

class QrRevokedScreen extends StatelessWidget {
  const QrRevokedScreen({super.key, this.details});

  final String? details;

  @override
  Widget build(BuildContext context) {
    return QrStatusScreen(
      title: 'QR révoqué',
      message: 'Ce QR a été désactivé par l’organisation.',
      icon: Icons.block_outlined,
      details: details,
    );
  }
}
