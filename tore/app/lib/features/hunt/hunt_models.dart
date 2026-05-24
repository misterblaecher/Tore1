class ActiveHunt {
  const ActiveHunt(
      {required this.id,
      required this.title,
      required this.description,
      required this.endsAt,
      required this.checkpointsCount,
      required this.myScore});
  final int id;
  final String title;
  final String description;
  final DateTime? endsAt;
  final int checkpointsCount;
  final int myScore;
  factory ActiveHunt.fromJson(Map<String, dynamic> json) => ActiveHunt(
        id: (json['id'] as num?)?.toInt() ?? 0,
        title: (json['title'] ?? 'Hunt').toString(),
        description: (json['description'] ?? '').toString(),
        endsAt: DateTime.tryParse((json['endsAt'] ?? '').toString()),
        checkpointsCount: (json['checkpointsCount'] as num?)?.toInt() ?? 0,
        myScore: (json['myScore'] as num?)?.toInt() ?? 0,
      );
  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'description': description,
        'endsAt': endsAt?.toIso8601String(),
        'checkpointsCount': checkpointsCount,
        'myScore': myScore
      };
}

class HuntClaimResponse {
  const HuntClaimResponse(
      {required this.ok,
      required this.alreadyClaimed,
      required this.pointsAwarded,
      required this.totalScore,
      required this.rewardTicketsAwarded});
  final bool ok;
  final bool alreadyClaimed;
  final int pointsAwarded;
  final int totalScore;
  final int rewardTicketsAwarded;
  factory HuntClaimResponse.fromJson(Map<String, dynamic> json) =>
      HuntClaimResponse(
        ok: json['ok'] == true,
        alreadyClaimed: json['alreadyClaimed'] == true,
        pointsAwarded: (json['pointsAwarded'] as num?)?.toInt() ?? 0,
        totalScore: (json['totalScore'] as num?)?.toInt() ?? 0,
        rewardTicketsAwarded:
            (json['rewardTicketsAwarded'] as num?)?.toInt() ?? 0,
      );
}

class HuntLeaderboard {
  const HuntLeaderboard(
      {required this.top3, required this.list, required this.me});
  final List<HuntLeaderboardRow> top3;
  final List<HuntLeaderboardRow> list;
  final HuntLeaderboardMe me;
  factory HuntLeaderboard.fromJson(Map<String, dynamic> json) =>
      HuntLeaderboard(
        top3: ((json['top3'] as List?) ?? const [])
            .map((e) => HuntLeaderboardRow.fromJson(
                Map<String, dynamic>.from(e as Map)))
            .toList(),
        list: ((json['list'] as List?) ?? const [])
            .map((e) => HuntLeaderboardRow.fromJson(
                Map<String, dynamic>.from(e as Map)))
            .toList(),
        me: HuntLeaderboardMe.fromJson(
            Map<String, dynamic>.from((json['me'] as Map?) ?? const {})),
      );
  Map<String, dynamic> toJson() => {
        'top3': top3.map((e) => e.toJson()).toList(),
        'list': list.map((e) => e.toJson()).toList(),
        'me': me.toJson()
      };
}

class HuntLeaderboardRow {
  const HuntLeaderboardRow(
      {required this.rank,
      required this.userId,
      required this.name,
      required this.score,
      required this.private});
  final int rank;
  final String userId;
  final String name;
  final int score;
  final bool private;
  factory HuntLeaderboardRow.fromJson(Map<String, dynamic> json) =>
      HuntLeaderboardRow(
        rank: (json['rank'] as num?)?.toInt() ?? 0,
        userId: (json['userId'] ?? '').toString(),
        name: (json['name'] ?? 'Player').toString(),
        score: (json['score'] as num?)?.toInt() ?? 0,
        private: json['private'] == true,
      );
  Map<String, dynamic> toJson() => {
        'rank': rank,
        'userId': userId,
        'name': name,
        'score': score,
        'private': private
      };
}

class HuntLeaderboardMe {
  const HuntLeaderboardMe(
      {required this.rank,
      required this.userId,
      required this.name,
      required this.score});
  final int? rank;
  final String userId;
  final String name;
  final int score;
  factory HuntLeaderboardMe.fromJson(Map<String, dynamic> json) =>
      HuntLeaderboardMe(
        rank: (json['rank'] as num?)?.toInt(),
        userId: (json['userId'] ?? '').toString(),
        name: (json['name'] ?? 'Me').toString(),
        score: (json['score'] as num?)?.toInt() ?? 0,
      );
  Map<String, dynamic> toJson() =>
      {'rank': rank, 'userId': userId, 'name': name, 'score': score};
}

class HuntStealResponse {
  const HuntStealResponse(
      {required this.ok,
      required this.result,
      required this.amount,
      this.attackerScore,
      this.victimScoreMasked});
  final bool ok;
  final String result;
  final int amount;
  final int? attackerScore;
  final Object? victimScoreMasked;
  factory HuntStealResponse.fromJson(Map<String, dynamic> json) =>
      HuntStealResponse(
        ok: json['ok'] == true,
        result: (json['result'] ?? 'BLOCKED').toString(),
        amount: (json['amount'] as num?)?.toInt() ?? 0,
        attackerScore: (json['attackerScore'] as num?)?.toInt(),
        victimScoreMasked: json['victimScoreMasked'],
      );
}
