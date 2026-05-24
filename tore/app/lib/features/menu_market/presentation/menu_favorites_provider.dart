import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

class MenuFavoritesController extends StateNotifier<Set<int>> {
  MenuFavoritesController(this.eventId) : super(const <int>{}) {
    _load();
  }

  final int eventId;

  String get _storageKey => 'menu_favorites_event_$eventId';

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    if (raw == null || raw.isEmpty) {
      state = const <int>{};
      return;
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is List) {
        state = decoded
            .map((entry) => int.tryParse(entry.toString()))
            .whereType<int>()
            .toSet();
      }
    } catch (_) {
      state = const <int>{};
    }
  }

  Future<void> toggle(int itemId) async {
    final next = {...state};
    if (next.contains(itemId)) {
      next.remove(itemId);
    } else {
      next.add(itemId);
    }
    state = next;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, jsonEncode(next.toList()));
  }
}

final menuFavoritesProvider =
    StateNotifierProvider.family<MenuFavoritesController, Set<int>, int>(
        (ref, eventId) {
  return MenuFavoritesController(eventId);
});
