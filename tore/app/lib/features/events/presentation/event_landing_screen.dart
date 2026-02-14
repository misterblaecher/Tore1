import 'package:flutter/material.dart';

class EventLandingScreen extends StatelessWidget {
  const EventLandingScreen({super.key, required this.eventId, required this.eventName});

  final int eventId;
  final String eventName;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(eventName)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.event_available_outlined, size: 42),
              const SizedBox(height: 12),
              Text('Event actif', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text('event_id: $eventId'),
              const SizedBox(height: 12),
              const Text('Le hub event sera enrichi dans une prochaine PR.'),
            ],
          ),
        ),
      ),
    );
  }
}
