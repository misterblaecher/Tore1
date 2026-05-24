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
