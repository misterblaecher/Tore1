import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import 'events_providers.dart';
import 'qr_pack_screen.dart';

class CreateEventScreen extends ConsumerStatefulWidget {
  const CreateEventScreen({super.key});

  @override
  ConsumerState<CreateEventScreen> createState() => _CreateEventScreenState();
}

class _CreateEventScreenState extends ConsumerState<CreateEventScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _barIdController = TextEditingController();
  final _cityController = TextEditingController();
  final _startsAtController = TextEditingController();
  final _endsAtController = TextEditingController();

  DateTime _startsAt = DateTime.now().add(const Duration(hours: 1));
  DateTime _endsAt = DateTime.now().add(const Duration(hours: 5));
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _startsAtController.text = _startsAt.toIso8601String();
    _endsAtController.text = _endsAt.toIso8601String();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _barIdController.dispose();
    _cityController.dispose();
    _startsAtController.dispose();
    _endsAtController.dispose();
    super.dispose();
  }

  Future<void> _pickDateTime({required bool isStart}) async {
    final initial = isStart ? _startsAt : _endsAt;
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
    );
    if (date == null) return;

    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initial),
    );
    if (time == null) return;

    final next = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    setState(() {
      if (isStart) {
        _startsAt = next;
        _startsAtController.text = _startsAt.toIso8601String();
      } else {
        _endsAt = next;
        _endsAtController.text = _endsAt.toIso8601String();
      }
    });
  }

  Future<void> _submit() async {
    final form = _formKey.currentState;
    if (form == null || !form.validate()) return;

    final barIdRaw = _barIdController.text.trim();
    final barId = barIdRaw.isEmpty ? null : int.tryParse(barIdRaw);
    if (barIdRaw.isNotEmpty && barId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Bar ID invalide.')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      final repo = ref.read(eventsRepositoryProvider);
      final created = await repo.createEvent(
        name: _nameController.text.trim(),
        startsAt: _startsAt,
        endsAt: _endsAt,
        barId: barId,
        city: _cityController.text.trim(),
      );

      ref.read(appContextProvider.notifier).enterEvent(
            eventId: created.eventId,
            eventName: created.name,
          );

      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => QrPackScreen(
            eventId: created.eventId,
            eventName: created.name,
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Création impossible.')),
      );
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Créer un event')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Nom',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Le nom est requis.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _startsAtController,
                readOnly: true,
                decoration: const InputDecoration(
                  labelText: 'Début',
                  border: OutlineInputBorder(),
                  suffixIcon: Icon(Icons.calendar_today_outlined),
                ),
                onTap: () => _pickDateTime(isStart: true),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _endsAtController,
                readOnly: true,
                decoration: const InputDecoration(
                  labelText: 'Fin',
                  border: OutlineInputBorder(),
                  suffixIcon: Icon(Icons.calendar_today_outlined),
                ),
                onTap: () => _pickDateTime(isStart: false),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _barIdController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Bar ID (optionnel)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _cityController,
                decoration: const InputDecoration(
                  labelText: 'Ville (optionnel)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _submitting ? null : _submit,
                icon: const Icon(Icons.check_circle_outline),
                label: Text(_submitting ? 'Création...' : 'Créer'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
