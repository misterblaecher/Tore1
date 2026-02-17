String orgaRoleFromInviteType(String raw) {
  final normalized = raw.trim().toUpperCase();
  switch (normalized) {
    case 'MANAGER':
    case 'STAFF':
    case 'FOLLOWER':
    case 'MEMBER':
      return normalized;
    default:
      return 'MEMBER';
  }
}
