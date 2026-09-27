class EventSharePayload {
  const EventSharePayload({
    required this.deeplink,
    required this.httpsLink,
    required this.qrPayloadJoin,
    this.eventCode,
  });

  final String deeplink;
  final String httpsLink;
  final String qrPayloadJoin;
  final String? eventCode;

  factory EventSharePayload.fromJson(Map<String, dynamic> json) {
    return EventSharePayload(
      deeplink: (json['deeplink'] ?? '').toString(),
      httpsLink: (json['https_link'] ?? '').toString(),
      qrPayloadJoin: (json['qr_payload_join'] ?? '').toString(),
      eventCode: json['event_code']?.toString(),
    );
  }
}

class CreateWizardState {
  const CreateWizardState({required this.step, this.publishNow = true});

  final int step;
  final bool publishNow;

  CreateWizardState next() =>
      CreateWizardState(step: step + 1, publishNow: publishNow);
  CreateWizardState prev() =>
      CreateWizardState(step: step > 0 ? step - 1 : 0, publishNow: publishNow);
}

const eventModuleLabels = <String, String>{
  'entry': 'Entrée',
  'bar': 'Bar',
  'ticker': 'Fil en direct',
  'music': 'Musique',
  'hunt': 'Chasse au trésor',
  'battles': 'Défis',
  'safety': 'Sécurité',
  'wifi': 'Wi-Fi',
  'map': 'Carte',
  'polymarket_event': 'Pronostics',
  'classement': 'Classement',
  'broadcast': 'Annonces',
};

const eventModulePresets = <String, Set<String>>{
  'Soirée classique': {'entry', 'bar', 'ticker'},
  'Concert': {'entry', 'bar', 'music', 'broadcast'},
  'Animation': {'entry', 'bar', 'hunt', 'classement'},
};

Map<String, bool> modulesForPreset(String name) => {
  for (final key in eventModuleLabels.keys)
    key: eventModulePresets[name]?.contains(key) ?? false,
};

int? parseEntryPriceCents(String value) {
  final normalized = value.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d+(\.\d{1,2})?$').hasMatch(normalized)) return null;
  final parts = normalized.split('.');
  final euros = int.tryParse(parts.first);
  if (euros == null || euros > 1000000) return null;
  final cents = parts.length == 2 ? int.parse(parts.last.padRight(2, '0')) : 0;
  return euros * 100 + cents;
}

String? validateEventCreate({
  required String name,
  required DateTime start,
  required DateTime end,
  required bool isFree,
  required String price,
  required String description,
}) {
  if (name.trim().isEmpty) return 'Ajoute un nom à l’event.';
  if (!end.isAfter(start)) return 'La fin doit être après le début.';
  if (description.trim().length > 280) {
    return 'La description doit faire 280 caractères maximum.';
  }
  final priceCents = isFree ? 0 : parseEntryPriceCents(price);
  if (!isFree && (priceCents == null || priceCents <= 0)) {
    return 'Saisis un prix valide supérieur à 0 € (deux décimales maximum).';
  }
  return null;
}

Map<String, dynamic> buildEventCreatePayload({
  required String name,
  required DateTime start,
  required DateTime end,
  required String visibility,
  required String hostType,
  String? hostId,
  required String venueName,
  required String venueAddress,
  required Map<String, bool> modulesOn,
  required bool isFree,
  required String price,
  required String description,
}) => {
  'name': name.trim(),
  'startAt': start.toUtc().toIso8601String(),
  'endAt': end.toUtc().toIso8601String(),
  'visibility': visibility,
  'host_type': hostType,
  if (hostId != null) 'host_id': hostId,
  'venue': {'name': venueName.trim(), 'address': venueAddress.trim()},
  'modulesOn': Map<String, bool>.from(modulesOn),
  'rulesFlags': <String, dynamic>{},
  'entry_price_cents': isFree ? 0 : parseEntryPriceCents(price)!,
  'currency': 'EUR',
  'public_description': description.trim(),
};
