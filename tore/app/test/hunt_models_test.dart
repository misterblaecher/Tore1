import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/hunt/hunt_models.dart';

void main() {
  test('parses active hunt payload', () {
    final model = ActiveHunt.fromJson({
      'id': 12,
      'title': 'Hunt Liège',
      'description': 'Find all checkpoints',
      'endsAt': '2026-01-01T00:00:00Z',
      'checkpointsCount': 8,
      'myScore': 120,
    });

    expect(model.id, 12);
    expect(model.title, 'Hunt Liège');
    expect(model.checkpointsCount, 8);
    expect(model.myScore, 120);
  });

  test('parses leaderboard payload', () {
    final lb = HuntLeaderboard.fromJson({
      'top3': [
        {'rank': 1, 'userId': 'u1', 'name': 'A', 'score': 100, 'private': false}
      ],
      'list': [
        {'rank': 1, 'userId': 'u1', 'name': 'A', 'score': 100, 'private': false},
        {'rank': 2, 'userId': 'u2', 'name': 'B', 'score': 90, 'private': true}
      ],
      'me': {'rank': 2, 'userId': 'u2', 'name': 'B', 'score': 90}
    });

    expect(lb.top3.first.rank, 1);
    expect(lb.list.length, 2);
    expect(lb.me.userId, 'u2');
  });
}
