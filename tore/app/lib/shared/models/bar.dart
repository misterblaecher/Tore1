class Bar {
  final int id;
  final String name;
  final String city;

  const Bar({
    required this.id,
    required this.name,
    required this.city,
  });

  factory Bar.fromJson(Map<String, dynamic> json) {
    return Bar(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      city: (json['city'] ?? '').toString(),
    );
  }
}
