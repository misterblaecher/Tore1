import 'package:flutter/material.dart';

class BarStaffScreen extends StatelessWidget {
  const BarStaffScreen({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Staff Bar')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.local_bar_outlined, size: 52),
              const SizedBox(height: 12),
              Text('Staff Bar — Event #$eventId',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              const Text(
                'Mode staff bar prêt pour les opérations live.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
