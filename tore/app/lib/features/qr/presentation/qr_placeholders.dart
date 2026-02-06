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

<<<<<<< HEAD
=======
class AdminConfigPlaceholder extends StatelessWidget {
  const AdminConfigPlaceholder({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context) {
    return _PlaceholderScaffold(
      title: 'Admin Config',
      eventId: eventId,
    );
  }
}

class StaffEntryPlaceholder extends StatelessWidget {
  const StaffEntryPlaceholder({
    super.key,
    required this.eventId,
    required this.modeLabel,
  });

  final int eventId;
  final String modeLabel;

  @override
  Widget build(BuildContext context) {
    return _PlaceholderScaffold(
      title: modeLabel,
      eventId: eventId,
    );
  }
}

>>>>>>> cccfa9d6d4f0e1ae9c1d17452eb3be68653b49bf
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
<<<<<<< HEAD
}
=======
}
>>>>>>> cccfa9d6d4f0e1ae9c1d17452eb3be68653b49bf
