/// Compatibility layer.
///
/// The app now centralizes auth + session providers in `lib/state.dart`.
/// We keep this file to avoid breaking imports in older screens.

export '../../state.dart' show authRepositoryProvider, meProvider, userIdProvider;
