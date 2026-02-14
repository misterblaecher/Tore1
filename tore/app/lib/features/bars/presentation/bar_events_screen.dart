import 'package:flutter/material.dart';

class BarEventsScreen extends StatelessWidget {
  const BarEventsScreen({super.key, required this.barId, required this.barName});

  final int barId;
  final String barName;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(barName)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Bar #$barId', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              const Text('Events loading…'),
            ],
          ),
        ),
      ),
    );
  }
}
