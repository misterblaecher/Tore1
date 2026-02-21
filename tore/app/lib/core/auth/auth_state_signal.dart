import 'dart:async';

class AuthStateSignal {
  AuthStateSignal._();

  static final AuthStateSignal instance = AuthStateSignal._();

  final StreamController<void> _unauthenticatedController = StreamController<void>.broadcast();

  Stream<void> get onUnauthenticated => _unauthenticatedController.stream;

  void notifyUnauthenticated() {
    if (!_unauthenticatedController.isClosed) {
      _unauthenticatedController.add(null);
    }
  }
}
