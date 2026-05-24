import 'app_environment.dart';

class LinkBuilder {
  LinkBuilder(this.environment);

  final AppEnvironment environment;

  String get httpsBase {
    switch (environment) {
      case AppEnvironment.dev:
        return 'https://dev.tore.app';
      case AppEnvironment.stage:
        return 'https://stage.tore.app';
      case AppEnvironment.prod:
        return 'https://tore.app';
    }
  }

  String get appBase => 'tore:/';

  String qr(String payload) => '$httpsBase/qr/${Uri.encodeComponent(payload)}';

  String appQr(String payload) => '$appBase/qr/${Uri.encodeComponent(payload)}';

  String event(String eventId) =>
      '$httpsBase/event/${Uri.encodeComponent(eventId)}';

  String appEvent(String eventId) =>
      '$appBase/event/${Uri.encodeComponent(eventId)}';

  String bar(String barId) => '$httpsBase/bar/${Uri.encodeComponent(barId)}';

  String appBar(String barId) => '$appBase/bar/${Uri.encodeComponent(barId)}';

  String menu(String scope, String id) =>
      '$httpsBase/menu/${Uri.encodeComponent(scope)}/${Uri.encodeComponent(id)}';

  String appMenu(String scope, String id) =>
      '$appBase/menu/${Uri.encodeComponent(scope)}/${Uri.encodeComponent(id)}';
}
