import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state.dart';
import 'runtime_write_guard.dart';

const readOnlyModeReasonMessage = 'Mode lecture: réseau indisponible.';

bool isReadOnly(WidgetRef ref) => ref.watch(isReadOnlyProvider);

bool isWriteBlocked({required bool readOnly, required bool runtimeBlocked}) {
  return readOnly || runtimeBlocked;
}

String writeBlockedMessage({required bool readOnly, String? runtimeState, String? runtimeReason}) {
  if (readOnly) return readOnlyModeReasonMessage;
  return writeBlockedReasonMessage(normalizeRuntimeBlockReason(state: runtimeState, reason: runtimeReason));
}
