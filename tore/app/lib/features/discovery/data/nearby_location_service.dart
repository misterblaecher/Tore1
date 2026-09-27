import 'package:geolocator/geolocator.dart';

class NearbyCoordinates {
  const NearbyCoordinates(this.lat, this.lng);

  final double lat;
  final double lng;
}

class NearbyLocationService {
  Future<NearbyCoordinates?> locate() async {
    if (!await Geolocator.isLocationServiceEnabled()) return null;

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return null;
    }

    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.medium,
        timeLimit: Duration(seconds: 8),
      ),
    );
    return NearbyCoordinates(position.latitude, position.longitude);
  }
}
