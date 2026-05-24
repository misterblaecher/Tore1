import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/qr_resolve.dart';
import 'package:tore/rebuild/routing/app_routes.dart';
import 'package:tore/rebuild/routing/qr_router.dart';

void main() {
  test('migrated QR order_client routes to rebuild adapter orders path', () {
    final router = QrRouter();

    expect(router.targetFor(const QrResolve(valid: true, type: 'order_client')),
        AppRoutes.orders);
  });

  test('blocks legacy route strings from routeFront mapping', () {
    final router = QrRouter();

    expect(
      router.targetFor(
          const QrResolve(valid: true, type: 'menu', routeFront: '/app_shell')),
      AppRoutes.blocked,
    );
    expect(
      router.targetFor(const QrResolve(
          valid: true, type: 'menu', routeFront: '/features/orders')),
      AppRoutes.blocked,
    );
  });
}
