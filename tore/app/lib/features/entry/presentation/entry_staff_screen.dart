import 'package:flutter/material.dart';

import 'entry_mode_screen.dart';

class EntryStaffScreen extends StatelessWidget {
  const EntryStaffScreen({super.key, required this.eventId});

  final int? eventId;

  @override
  Widget build(BuildContext context) {
    return EntryModeScreen(eventId: eventId);
  }
}
