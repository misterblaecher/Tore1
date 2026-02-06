import 'package:flutter/material.dart';

class QrForbiddenScreen extends StatelessWidget {
  const QrForbiddenScreen({super.key, required this.roleRequired});

  final String roleRequired;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Accès refusé'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Accès refusé – rôle requis : ${roleRequired.toUpperCase()}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            const Text(
              'Ce QR nécessite un niveau d’accès supérieur.',
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.arrow_back),
                label: const Text('Retour'),
              ),
            ),
          ],
        ),
      ),
    );
  }
<<<<<<< HEAD
}
=======
}
>>>>>>> cccfa9d6d4f0e1ae9c1d17452eb3be68653b49bf
