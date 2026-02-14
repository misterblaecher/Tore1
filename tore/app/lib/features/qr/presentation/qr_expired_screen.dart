import 'package:flutter/material.dart';

import 'qr_status_screen.dart';

class QrExpiredScreen extends StatelessWidget {
  const QrExpiredScreen({super.key, this.details});

  final String? details;

  @override
  Widget build(BuildContext context) {
    return QrStatusScreen(
      title: 'QR expiré',
      message: 'Ce QR n’est plus valide. Demande un nouveau code.',
      icon: Icons.schedule_outlined,
      details: details,
    );
  }
}
