enum MusicProvider {
  spotify,
  apple,
  youtubeMusic,
  soundcloud,
}

MusicProvider? musicProviderFromApi(String raw) {
  switch (raw.trim().toLowerCase()) {
    case 'spotify':
      return MusicProvider.spotify;
    case 'apple':
      return MusicProvider.apple;
    case 'youtube_music':
    case 'ytmusic':
      return MusicProvider.youtubeMusic;
    case 'soundcloud':
      return MusicProvider.soundcloud;
    default:
      return null;
  }
}

String musicProviderApiValue(MusicProvider provider) {
  switch (provider) {
    case MusicProvider.spotify:
      return 'spotify';
    case MusicProvider.apple:
      return 'apple';
    case MusicProvider.youtubeMusic:
      return 'youtube_music';
    case MusicProvider.soundcloud:
      return 'soundcloud';
  }
}

String musicProviderLabel(MusicProvider provider) {
  switch (provider) {
    case MusicProvider.spotify:
      return 'Spotify';
    case MusicProvider.apple:
      return 'Apple Music';
    case MusicProvider.youtubeMusic:
      return 'YouTube Music';
    case MusicProvider.soundcloud:
      return 'SoundCloud';
  }
}

bool isLocallyValidCandidateLink(String raw, MusicProvider provider) {
  final uri = Uri.tryParse(raw.trim());
  if (uri == null || uri.scheme != 'https' || (uri.host.isEmpty)) return false;
  final host = uri.host.toLowerCase();
  switch (provider) {
    case MusicProvider.youtubeMusic:
      return host.contains('youtube.com') ||
          host == 'youtu.be' ||
          host == 'music.youtube.com';
    case MusicProvider.soundcloud:
      return host == 'soundcloud.com' && uri.pathSegments.length >= 2;
    case MusicProvider.spotify:
      return host.contains('spotify.com');
    case MusicProvider.apple:
      return host.contains('apple.com');
  }
}

String candidateShortLink(String raw) {
  final uri = Uri.tryParse(raw);
  if (uri == null) return raw;
  final path =
      uri.path.length > 28 ? '${uri.path.substring(0, 28)}…' : uri.path;
  return '${uri.host}$path';
}
