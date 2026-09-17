import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/remote_config.dart';
import '../../core/network/network_state_provider.dart';
import '../../state.dart';
import 'runtime_write_guard.dart';

enum WriteIntent { critical, nonCritical }

const readOnlyModeReasonMessage = 'Mode lecture: réseau indisponible.';
const degradedModeReasonMessage =
    'Réseau instable: cette action sensible est temporairement bloquée.';

bool isReadOnly(WidgetRef ref) {
  final bootReadOnly = ref.watch(isReadOnlyProvider);
  final networkState = ref.watch(networkStatusProvider);
  return bootReadOnly || networkState == NetworkState.offline;
}

bool isWriteDegradedBlocked(WidgetRef ref, WriteIntent intent) {
  final networkState = ref.watch(networkStatusProvider);
  return networkState == NetworkState.degraded &&
      intent == WriteIntent.critical;
}

bool canWrite(WidgetRef ref,
    {required WriteIntent intent, bool runtimeBlocked = false}) {
  if (isReadOnly(ref)) return false;
  if (isWriteDegradedBlocked(ref, intent)) return false;
  if (runtimeBlocked) return false;
  return true;
}

String? writeDisabledReason(WidgetRef ref,
    {required WriteIntent intent,
    String? runtimeState,
    String? runtimeReason}) {
  final remoteMessage = ref.watch(remoteWriteMessageProvider);
  if (remoteMessage != null) return remoteMessage;
  if (isReadOnly(ref)) return readOnlyModeReasonMessage;
  if (isWriteDegradedBlocked(ref, intent)) return degradedModeReasonMessage;
  final runtimeNormalized =
      normalizeRuntimeBlockReason(state: runtimeState, reason: runtimeReason);
  if (runtimeNormalized != null)
    return writeBlockedReasonMessage(runtimeNormalized);
  return null;
}

bool isWriteBlocked(
    {required bool readOnly,
    required bool runtimeBlocked,
    bool degradedBlocked = false}) {
  return readOnly || degradedBlocked || runtimeBlocked;
}

String writeBlockedMessage(
    {required bool readOnly,
    bool degradedBlocked = false,
    String? runtimeState,
    String? runtimeReason}) {
  if (readOnly) return readOnlyModeReasonMessage;
  if (degradedBlocked) return degradedModeReasonMessage;
  return writeBlockedReasonMessage(
      normalizeRuntimeBlockReason(state: runtimeState, reason: runtimeReason));
}
