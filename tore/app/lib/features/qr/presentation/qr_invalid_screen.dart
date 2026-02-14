import 'package:flutter/material.dart';

import 'qr_status_screen.dart';

class QrInvalidScreen extends StatelessWidget {
  const QrInvalidScreen({super.key, this.details});

  final String? details;

  @override
  Widget build(BuildContext context) {
    return QrStatusScreen(
      title: 'QR invalide',
      message: 'Le format ou la signature du QR est invalide.',
      icon: Icons.error_outline,
      details: details,
    );
  }
}
