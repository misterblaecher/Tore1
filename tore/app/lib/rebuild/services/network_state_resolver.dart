import '../models/rebuild_types.dart';

class NetworkStateResolver {
  bool canReadRemote(ConnectivityState state) => state != ConnectivityState.offline;

  bool canWrite(ConnectivityState state) => state != ConnectivityState.offline;

  int getMaxGetRetries(ConnectivityState state) => state == ConnectivityState.degraded ? 2 : 0;
}
