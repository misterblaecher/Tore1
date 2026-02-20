import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/events/presentation/music_vote_models.dart';

void main() {
  test('provider parsing supports youtube_music and soundcloud', () {
    expect(musicProviderFromApi('youtube_music'), MusicProvider.youtubeMusic);
    expect(musicProviderFromApi('ytmusic'), MusicProvider.youtubeMusic);
    expect(musicProviderFromApi('soundcloud'), MusicProvider.soundcloud);
  });

  test('local link validation happy and invalid cases', () {
    expect(isLocallyValidCandidateLink('https://music.youtube.com/watch?v=abc', MusicProvider.youtubeMusic), isTrue);
    expect(isLocallyValidCandidateLink('http://music.youtube.com/watch?v=abc', MusicProvider.youtubeMusic), isFalse);
    expect(isLocallyValidCandidateLink('https://soundcloud.com/artist/title', MusicProvider.soundcloud), isTrue);
    expect(isLocallyValidCandidateLink('https://soundcloud.com/discover', MusicProvider.soundcloud), isFalse);
  });

  test('provider label mapping', () {
    expect(musicProviderLabel(MusicProvider.youtubeMusic), 'YouTube Music');
    expect(musicProviderLabel(MusicProvider.soundcloud), 'SoundCloud');
  });
}
