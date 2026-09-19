# Migration compatibility matrix

Every migration PR must preserve these upgrade paths:

1. empty PostgreSQL database -> `alembic upgrade head`;
2. retired public-event lineage (`0013_public_event_recap`) -> current head;
3. previous deployed head (N-1) -> current head;
4. representative legacy forum/workspace schema -> current head.

The PostgreSQL scenarios run in isolated synthetic databases created by CI. After
upgrade, the tests compare database tables and columns with `Base.metadata`.
The existing legacy fixture keeps representative historical rows and verifies
that the bridge migrations retain their data.

Already-deployed Alembic revisions are immutable. Repairs must be introduced as
new revisions or merge revisions. Never place a production dump containing user
data in CI; fixtures must be structural or synthetic.
