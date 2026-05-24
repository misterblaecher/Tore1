class BattleStatePayload {
  const BattleStatePayload(
      {required this.round,
      required this.counts,
      required this.myChoice,
      required this.status});
  final BattleRound? round;
  final Map<String, int> counts;
  final String? myChoice;
  final String status;
  factory BattleStatePayload.fromJson(Map<String, dynamic> json) =>
      BattleStatePayload(
          round: json['round'] is Map
              ? BattleRound.fromJson(
                  Map<String, dynamic>.from(json['round'] as Map))
              : null,
          counts: ((json['counts'] as Map?) ?? const {})
              .map((k, v) => MapEntry(k.toString(), (v as num?)?.toInt() ?? 0)),
          myChoice: json['myChoice']?.toString(),
          status: json['status']?.toString() ?? 'IDLE');
  Map<String, dynamic> toJson() => {
        'round': round?.toJson(),
        'counts': counts,
        'myChoice': myChoice,
        'status': status
      };
}

class BattleRound {
  const BattleRound(
      {required this.id,
      required this.title,
      required this.kind,
      required this.status,
      this.optionALabel,
      this.optionBLabel,
      this.endsAt,
      this.winner});
  final int id;
  final String title;
  final String kind;
  final String status;
  final String? optionALabel;
  final String? optionBLabel;
  final String? endsAt;
  final String? winner;
  factory BattleRound.fromJson(Map<String, dynamic> json) => BattleRound(
      id: (json['id'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      kind: json['kind']?.toString() ?? 'PARTICIPATION',
      status: json['status']?.toString() ?? 'IDLE',
      optionALabel: json['optionALabel']?.toString(),
      optionBLabel: json['optionBLabel']?.toString(),
      endsAt: json['endsAt']?.toString(),
      winner: json['winner']?.toString());
  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'kind': kind,
        'status': status,
        'optionALabel': optionALabel,
        'optionBLabel': optionBLabel,
        'endsAt': endsAt,
        'winner': winner
      };
}

class BattleLeaderboard {
  const BattleLeaderboard(
      {required this.top3,
      required this.list,
      required this.me,
      required this.rulesText});
  final List<BattleLeaderboardRow> top3;
  final List<BattleLeaderboardRow> list;
  final BattleLeaderboardRow? me;
  final String rulesText;
  factory BattleLeaderboard.fromJson(Map<String, dynamic> json) =>
      BattleLeaderboard(
          top3: ((json['top3'] as List?) ?? const [])
              .map((e) => BattleLeaderboardRow.fromJson(
                  Map<String, dynamic>.from(e as Map)))
              .toList(),
          list: ((json['list'] as List?) ?? const [])
              .map((e) => BattleLeaderboardRow.fromJson(
                  Map<String, dynamic>.from(e as Map)))
              .toList(),
          me: json['me'] is Map
              ? BattleLeaderboardRow.fromJson(
                  Map<String, dynamic>.from(json['me'] as Map))
              : null,
          rulesText: json['rulesText']?.toString() ?? '');
  Map<String, dynamic> toJson() => {
        'top3': top3.map((e) => e.toJson()).toList(),
        'list': list.map((e) => e.toJson()).toList(),
        'me': me?.toJson(),
        'rulesText': rulesText
      };
}

class BattleLeaderboardRow {
  const BattleLeaderboardRow(
      {required this.rank,
      required this.userId,
      required this.name,
      required this.score});
  final int rank;
  final String userId;
  final String name;
  final int score;
  factory BattleLeaderboardRow.fromJson(Map<String, dynamic> json) =>
      BattleLeaderboardRow(
          rank: (json['rank'] as num?)?.toInt() ?? 0,
          userId: json['userId']?.toString() ?? '',
          name: json['name']?.toString() ?? '',
          score: (json['score'] as num?)?.toInt() ?? 0);
  Map<String, dynamic> toJson() =>
      {'rank': rank, 'userId': userId, 'name': name, 'score': score};
}
