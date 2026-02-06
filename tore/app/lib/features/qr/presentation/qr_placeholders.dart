import 'package:flutter/material.dart';

class JoinEventPlaceholder extends StatelessWidget {
  const JoinEventPlaceholder({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context) {
    return _PlaceholderScaffold(
      title: 'Join Event',
      eventId: eventId,
    );
  }
}

class MenuPlaceholder extends StatelessWidget {
  const MenuPlaceholder({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context) {
    return _PlaceholderScaffold(
      title: 'Menu Event',
      eventId: eventId,
    );
  }
}

class EntryPlaceholder extends StatelessWidget {
  const EntryPlaceholder({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context) {
    return _PlaceholderScaffold(
      title: 'Entry Event',
      eventId: eventId,
    );
  }
}

class _PlaceholderScaffold extends StatelessWidget {
  const _PlaceholderScaffold({required this.title, required this.eventId});

  final String title;
  final int eventId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text('event_id: $eventId'),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.arrow_back),
                label: const Text('Retour'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}