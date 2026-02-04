class ApiException implements Exception {
  final int? statusCode;
  final String message;
  final dynamic details;

  ApiException(this.message, {this.statusCode, this.details});

  @override
  String toString() => 'ApiException($statusCode): $message';
}
