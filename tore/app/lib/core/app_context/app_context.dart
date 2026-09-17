import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kLastBarId = 'ctx_last_bar_id';
const _kLastBarName = 'ctx_last_bar_name';
const _kLastEventId = 'ctx_last_event_id';
const _kLastEventName = 'ctx_last_event_name';
const _kLastEventModules = 'ctx_last_event_modules';

class AppContextState {
  final int? selectedBarId;
  final String? selectedBarName;
  final int? activeEventId;
  final String? activeEventName;
  final Map<String, bool>? activeEventModules;

  const AppContextState({
    this.selectedBarId,
    this.selectedBarName,
    this.activeEventId,
    this.activeEventName,
    this.activeEventModules,
  });

  bool get hasActiveEvent => activeEventId != null;

  AppContextState copyWith({
    int? selectedBarId,
    String? selectedBarName,
    int? activeEventId,
    String? activeEventName,
    Map<String, bool>? activeEventModules,
    bool clearEvent = false,
    bool clearBar = false,
  }) {
    return AppContextState(
      selectedBarId: clearBar ? null : (selectedBarId ?? this.selectedBarId),
      selectedBarName:
          clearBar ? null : (selectedBarName ?? this.selectedBarName),
      activeEventId: clearEvent ? null : (activeEventId ?? this.activeEventId),
      activeEventName:
          clearEvent ? null : (activeEventName ?? this.activeEventName),
      activeEventModules:
          clearEvent ? null : (activeEventModules ?? this.activeEventModules),
    );
  }
}

class AppContextController extends StateNotifier<AppContextState> {
  AppContextController() : super(const AppContextState());

  SharedPreferences? _prefs;

  void attachPrefs(SharedPreferences prefs) {
    _prefs = prefs;
  }

  Future<void> restoreLastContext() async {
    final prefs = _prefs;
    if (prefs == null) return;

    final barId = prefs.getInt(_kLastBarId);
    final barName = prefs.getString(_kLastBarName);
    final eventId = prefs.getInt(_kLastEventId);
    final eventName = prefs.getString(_kLastEventName);
    final eventModulesRaw = prefs.getString(_kLastEventModules);
    Map<String, bool>? eventModules;
    if (eventModulesRaw != null && eventModulesRaw.isNotEmpty) {
      try {
        final decoded = jsonDecode(eventModulesRaw);
        if (decoded is Map) {
          eventModules = decoded
              .map((key, value) => MapEntry(key.toString(), value == true));
        }
      } catch (_) {
        eventModules = null;
      }
    }

    state = state.copyWith(
      selectedBarId: barId,
      selectedBarName: barName,
      activeEventId: eventId,
      activeEventName: eventName,
      activeEventModules: eventModules,
    );
  }

  void setBar({required int barId, required String barName}) {
    state = state.copyWith(selectedBarId: barId, selectedBarName: barName);
    _prefs?.setInt(_kLastBarId, barId);
    _prefs?.setString(_kLastBarName, barName);
  }

  void enterEvent({
    required int eventId,
    required String eventName,
    Map<String, bool>? activeEventModules,
  }) {
    final modules = activeEventModules ??
        (state.activeEventId == eventId
            ? state.activeEventModules ?? const <String, bool>{}
            : const <String, bool>{});
    state = state.copyWith(
      activeEventId: eventId,
      activeEventName: eventName,
      activeEventModules: modules,
    );
    _prefs?.setInt(_kLastEventId, eventId);
    _prefs?.setString(_kLastEventName, eventName);
    _prefs?.setString(_kLastEventModules, jsonEncode(modules));
  }

  void setActiveEventModules(Map<String, bool> modules) {
    state = state.copyWith(activeEventModules: modules);
    _prefs?.setString(_kLastEventModules, jsonEncode(modules));
  }

  void leaveEvent() {
    state = state.copyWith(clearEvent: true);
    _prefs?.remove(_kLastEventId);
    _prefs?.remove(_kLastEventName);
    _prefs?.remove(_kLastEventModules);
  }

  void clearAll() {
    state = state.copyWith(clearBar: true, clearEvent: true);
    _prefs?.remove(_kLastBarId);
    _prefs?.remove(_kLastBarName);
    _prefs?.remove(_kLastEventId);
    _prefs?.remove(_kLastEventName);
    _prefs?.remove(_kLastEventModules);
  }
}

final appContextProvider =
    StateNotifierProvider<AppContextController, AppContextState>((ref) {
  return AppContextController();
});

/// Initializes the app context controller with SharedPreferences and restores the last selection.
final appContextInitProvider = FutureProvider<void>((ref) async {
  final prefs = await SharedPreferences.getInstance();
  final ctrl = ref.read(appContextProvider.notifier);
  ctrl.attachPrefs(prefs);
  await ctrl.restoreLastContext();
});
