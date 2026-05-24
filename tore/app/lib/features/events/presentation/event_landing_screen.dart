import 'package:flutter/material.dart';

import 'event_hub_screen.dart';

@Deprecated('Use EventHubScreen instead.')
class EventLandingScreen extends StatelessWidget {
  const EventLandingScreen(
      {super.key, required this.eventId, required this.eventName});

  final int eventId;
  final String eventName;

  @override
  Widget build(BuildContext context) {
    return EventHubScreen(eventId: eventId, eventName: eventName);
  }
}
