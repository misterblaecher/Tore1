import 'package:flutter/material.dart';
import 'admin_prices.dart';
import 'admin_tickets.dart';

class OrganizerScreen extends StatelessWidget {
  const OrganizerScreen({super.key, required this.eventId});
  final int eventId;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text('Organisateur — Event #$eventId'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Prix'),
              Tab(text: 'Tickets'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            AdminPricesScreen(eventId: eventId),
            AdminTicketsScreen(eventId: eventId),
          ],
        ),
      ),
    );
  }
}
