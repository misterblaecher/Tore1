import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/network/error_mapper.dart';

void main() {
  test('normalizes historical QR/backend reason aliases', () {
    expect(normalizeToreErrorCode('expired_qr'), 'qr_expired');
    expect(normalizeToreErrorCode('replay'), 'qr_replay');
    expect(normalizeToreErrorCode('missing_token'), 'unauthenticated');
    expect(normalizeToreErrorCode('event_not_found'), 'not_found');
    expect(normalizeToreErrorCode('validation_error'), 'invalid_request');
    expect(normalizeToreErrorCode('offline'), 'offline_write_blocked');
  });

  test('resolves useful canonical UX copy', () {
    final expired = resolveToreUiError('expired');
    expect(expired.code, 'qr_expired');
    expect(expired.title, 'QR expiré');

    final paused = resolveToreUiError('event_paused');
    expect(paused.code, 'event_paused');
    expect(paused.message, contains('temporairement'));

    final unknown = resolveToreUiError('does_not_exist');
    expect(unknown.code, 'qr_unknown');
  });
}
