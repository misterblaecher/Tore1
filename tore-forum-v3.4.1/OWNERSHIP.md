# OWNERSHIP — TORÈ Forum v3.4

## Invariant
1. `Structure.ownerUserId` pointe vers un User existant.
2. Ce User a un StructureMember ACTIVE.
3. Ce membership utilise le rôle système Owner.
4. `Owner.systemRole === true`.
5. Il existe exactement un membership Owner ACTIVE.

`StructureService.assertValidOwnership(structureId)` vérifie l’invariant.

## Interdictions hors transfert
L’Owner courant ne peut pas : changer de rôle, être révoqué, passer Alumni, recevoir une fin de mandat, supprimer/renommer le rôle Owner ou lui retirer les permissions critiques.

## Transfert
`StructureService.transferOwnership(newOwnerUserId)` vérifie l’acteur et la cible, garantit un rôle Bureau de repli, promeut la cible, rétrograde l’ancien Owner, met à jour `ownerUserId`, valide l’invariant, rollback en cas d’échec et écrit `OWNERSHIP_TRANSFERRED`.
