const now = new Date('2026-09-11T10:00:00+02:00');
const d = (days, hour=18, minute=0) => {const x=new Date(now);x.setDate(x.getDate()+days);x.setHours(hour,minute,0,0);return x.toISOString()};
const perms={
 owner:['structure.admin','structure.manage','ownership.transfer','members.view','members.manage','roles.manage','events.view','events.manage','events.publish','documents.view','documents.download','documents.manage','albums.view','albums.manage','folklore.view','folklore.manage','planning.view','planning.manage','stats.view','accounting.view','accounting.manage','accounting.unlock','visibility.manage','audit.view','channels.post','channels.manage','publications.manage','archives.view'],
 bureau:['members.view','members.manage','events.view','events.manage','events.publish','documents.view','documents.download','documents.manage','albums.view','albums.manage','folklore.view','folklore.manage','planning.view','planning.manage','stats.view','accounting.view','visibility.manage','channels.post','channels.manage','publications.manage','archives.view'],
 treasury:['members.view','events.view','events.manage','documents.view','documents.download','documents.manage','albums.view','folklore.view','planning.view','planning.manage','stats.view','accounting.view','accounting.manage','channels.post','archives.view'],
 staff:['members.view','events.view','events.manage','documents.view','documents.download','documents.manage','albums.view','albums.manage','folklore.view','planning.view','planning.manage','stats.view','channels.post','archives.view'],
 member:['members.view','events.view','documents.view','documents.download','albums.view','folklore.view','planning.view','channels.post','archives.view']
};
export const seed={
 version:5,currentUserId:'u_owner',activeStructureId:'s_lembuscade',
 users:[
  {id:'u_owner',name:'Louis Dubois',email:'louis@tore.be',initials:'LD'},
  {id:'u_marie',name:'Marie Colson',email:'marie@tore.be',initials:'MC'},
  {id:'u_thomas',name:'Thomas Renard',email:'thomas@tore.be',initials:'TR'},
  {id:'u_sophie',name:'Sophie Collin',email:'sophie@tore.be',initials:'SC'},
  {id:'u_jules',name:'Jules Bertrand',email:'jules@tore.be',initials:'JB'},
  {id:'u_emma',name:'Emma Laurent',email:'emma@tore.be',initials:'EL'},
  {id:'u_other',name:'Camille Martin',email:'camille@autre.be',initials:'CM'}
 ],
 structures:[
  {id:'s_lembuscade',slug:'lembuscade',name:'L’Embuscade',type:'Comité étudiant',status:'ACTIVE',ownerUserId:'u_owner',description:'Comité étudiant liégeois. Des soirées, du folklore et une mémoire qui se transmet.',shortDescription:'Plus qu’un comité, une mémoire vivante.',logo:'assets/app_icon.png',banner:null,accent:'#f6a800',secondaryAccent:'#20252a',logoBlobKey:null,bannerBlobKey:null,founded:2014,contact:{email:'contact@lembuscade.be',phone:'+32 4 000 00 00',address:'Liège, Belgique',instagram:'@lembuscade.tore',website:'https://tore.be'},sponsors:[{name:'Brasserie partenaire',url:'#'},{name:'Imprimerie du Carré',url:'#'}],seo:{index:true,title:'L’Embuscade — TORÈ Forum',description:'Page officielle de L’Embuscade sur TORÈ Forum.'},toreIntegration:{structureKey:'TORE-LEMBUSCADE',appSyncEnabled:true}},
  {id:'s_autre',slug:'autre-structure',name:'Autre Structure',type:'Cercle',status:'ACTIVE',ownerUserId:'u_other',description:'Structure de test multi-tenant.',shortDescription:'Isolation tenant.',logo:'assets/app_icon.png',banner:null,accent:'#6aa9ff',secondaryAccent:'#20252a',logoBlobKey:null,bannerBlobKey:null,founded:2020,contact:{email:'contact@autre.be',phone:'',address:'Liège, Belgique',instagram:'',website:''},sponsors:[],seo:{index:false,title:'Autre Structure — TORÈ Forum',description:'Structure de test.'},toreIntegration:{structureKey:'TORE-AUTRE',appSyncEnabled:false}}
 ],
 roles:[
  {id:'r_owner',structureId:'s_lembuscade',name:'Owner',systemRole:true,audienceLevel:'Privé',permissions:perms.owner},
  {id:'r_bureau',structureId:'s_lembuscade',name:'Bureau',audienceLevel:'Bureau',permissions:perms.bureau},
  {id:'r_tresorier',structureId:'s_lembuscade',name:'Trésorerie',audienceLevel:'Trésorerie',permissions:perms.treasury},
  {id:'r_staff',structureId:'s_lembuscade',name:'Staff',audienceLevel:'Staff',permissions:perms.staff},
  {id:'r_member',structureId:'s_lembuscade',name:'Membre',audienceLevel:'Membres',permissions:perms.member},
  {id:'r_other_owner',structureId:'s_autre',name:'Owner',systemRole:true,audienceLevel:'Privé',permissions:perms.owner}
 ],
 members:[
  {id:'m1',structureId:'s_lembuscade',userId:'u_owner',roleId:'r_owner',title:'Président',team:'Bureau',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Coordination générale','Représentation'],publicProfile:true,publicAlumni:false,notes:''},
  {id:'m2',structureId:'s_lembuscade',userId:'u_marie',roleId:'r_tresorier',title:'Trésorière',team:'Bureau',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Budget','Pièces justificatives'],publicProfile:true,publicAlumni:false,notes:''},
  {id:'m3',structureId:'s_lembuscade',userId:'u_thomas',roleId:'r_staff',title:'Responsable Sponsors',team:'Partenariats',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Sponsors','Conventions'],publicProfile:false,publicAlumni:false,notes:''},
  {id:'m4',structureId:'s_lembuscade',userId:'u_sophie',roleId:'r_staff',title:'Communication',team:'Communication',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Réseaux','Visuels'],publicProfile:true,publicAlumni:false,notes:''},
  {id:'m5',structureId:'s_lembuscade',userId:'u_jules',roleId:'r_bureau',title:'Vice-président',team:'Bureau',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Organisation'],publicProfile:true,publicAlumni:false,notes:''},
  {id:'m6',structureId:'s_lembuscade',userId:'u_emma',roleId:'r_member',title:'Responsable Bar',team:'Bar',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Bar','Stocks'],publicProfile:false,publicAlumni:false,notes:''},
  {id:'m_other',structureId:'s_autre',userId:'u_other',roleId:'r_other_owner',title:'Présidente',team:'Bureau',startDate:'2026-07-01',endDate:'2027-06-30',status:'ACTIVE',responsibilities:['Administration'],publicProfile:true,publicAlumni:false,notes:''}
 ],
 invitations:[
  {id:'inv1',structureId:'s_lembuscade',email:'camille@example.be',roleId:'r_member',status:'PENDING',expiresAt:d(5),createdAt:d(-2),method:'email',token:'invite-camille'},
  {id:'inv2',structureId:'s_lembuscade',email:'nora@example.be',roleId:'r_staff',status:'PENDING',expiresAt:d(3),createdAt:d(-1),method:'link',token:'invite-nora'}
 ],
 events:[
  {id:'e1',structureId:'s_lembuscade',slug:'tournoi-flechettes-septembre',title:'Tournoi de fléchettes',description:'Tournoi amical et soirée de rentrée.',cover:null,organizer:'L’Embuscade',coOrganizers:[],place:'Chez Mémé, Liège',barId:null,startAt:d(1,20),endAt:d(2,1),capacity:220,price:0,conditions:'Entrée libre dans la limite des places disponibles.',visibility:'Public',modules:['checkin','qr'],status:'PUBLISHED',appSyncStatus:'READY',staffMemberIds:['m1','m4','m6'],albumId:null,recap:null,publicSummary:false,documents:[]},
  {id:'e2',structureId:'s_lembuscade',slug:'rentree-lembuscade-2026',title:'Rentrée de L’Embuscade',description:'La grande rentrée du comité.',cover:null,organizer:'L’Embuscade',coOrganizers:['Cercle X'],place:'Le Carré, Liège',barId:null,startAt:d(8,22),endAt:d(9,4),capacity:650,price:5,conditions:'18+ · Respect de la charte TORÈ.',visibility:'Utilisateurs TORÈ',modules:['checkin','qr','feed'],status:'DRAFT',appSyncStatus:'NOT_PUBLISHED',staffMemberIds:['m1','m2','m3','m4'],albumId:null,recap:null,publicSummary:false,documents:['doc3']},
  {id:'e3',structureId:'s_lembuscade',slug:'summer-closing-2026',title:'Summer Closing 2026',description:'Clôture de l’année académique.',cover:null,organizer:'L’Embuscade',coOrganizers:[],place:'Liège',barId:null,startAt:'2026-06-20T21:00:00+02:00',endAt:'2026-06-21T03:30:00+02:00',capacity:700,price:7,conditions:'',visibility:'Public',modules:['checkin','qr'],status:'CLOSED',appSyncStatus:'ENDED',staffMemberIds:['m1','m2','m4'],albumId:'a1',recap:'642 entrées et une très bonne dynamique de soirée.',publicSummary:false,documents:['doc2']},
  {id:'e_other',structureId:'s_autre',slug:'event-secret-autre',title:'Événement Autre Structure',description:'Ne doit jamais fuiter.',cover:null,organizer:'Autre Structure',coOrganizers:[],place:'Secret',barId:null,startAt:d(4,20),endAt:d(5,1),capacity:100,price:0,conditions:'',visibility:'Privé',modules:[],status:'DRAFT',appSyncStatus:'NOT_PUBLISHED',staffMemberIds:[],albumId:null,recap:null,publicSummary:false,documents:[]}
 ],
 channels:[
  {id:'c1',structureId:'s_lembuscade',category:'Bureau',name:'bureau',description:'Coordination générale du comité',visibility:'Bureau',archived:false,pinnedMessageIds:['msg1']},
  {id:'c2',structureId:'s_lembuscade',category:'Organisation',name:'events',description:'Préparation des événements',visibility:'Staff',archived:false,pinnedMessageIds:[]},
  {id:'c3',structureId:'s_lembuscade',category:'Organisation',name:'communication',description:'Visuels et annonces',visibility:'Staff',archived:false,pinnedMessageIds:[]},
  {id:'c4',structureId:'s_lembuscade',category:'Gestion',name:'comptabilite',description:'Budget et justificatifs',visibility:'Trésorerie',archived:false,pinnedMessageIds:[]},
  {id:'c_other',structureId:'s_autre',category:'Privé',name:'secret',description:'Salon autre tenant',visibility:'Privé',archived:false,pinnedMessageIds:[]}
 ],
 messages:[
  {id:'msg1',structureId:'s_lembuscade',channelId:'c1',authorUserId:'u_owner',body:'Planning du second quadrimestre et points d’attention.',createdAt:d(-2,10),threadId:null,reactions:{'👍':['u_marie','u_jules']},attachmentDocumentId:null},
  {id:'msg2',structureId:'s_lembuscade',channelId:'c4',authorUserId:'u_marie',body:'Budget confidentiel : il manque deux justificatifs.',createdAt:d(-1,11),threadId:null,reactions:{'👍':['u_owner']},attachmentDocumentId:'doc2'},
  {id:'msg3',structureId:'s_lembuscade',channelId:'c2',authorUserId:'u_thomas',body:'Le sponsor principal confirme sa présence pour la rentrée.',createdAt:d(-1,14),threadId:null,reactions:{'❤️':['u_owner','u_sophie']},attachmentDocumentId:null},
  {id:'msg4',structureId:'s_lembuscade',channelId:'c3',authorUserId:'u_sophie',body:'Le visuel final est prêt pour validation.',createdAt:d(0,9),threadId:null,reactions:{},attachmentDocumentId:'doc4'},
  {id:'msg_other',structureId:'s_autre',channelId:'c_other',authorUserId:'u_other',body:'Message cross-tenant secret',createdAt:d(-1),threadId:null,reactions:{},attachmentDocumentId:null}
 ],
 threads:[],
 folders:[
  {id:'f1',structureId:'s_lembuscade',name:'Organisation',parentId:null},{id:'f2',structureId:'s_lembuscade',name:'Bureau',parentId:'f1'},{id:'f3',structureId:'s_lembuscade',name:'Events',parentId:'f1'},{id:'f4',structureId:'s_lembuscade',name:'Sponsors',parentId:null},{id:'f5',structureId:'s_lembuscade',name:'Factures',parentId:null},{id:'f_other',structureId:'s_autre',name:'Privé',parentId:null}
 ],
 documents:[
  {id:'doc1',structureId:'s_lembuscade',folderId:'f2',name:'Convention partenaire.pdf',description:'Convention annuelle.',mime:'application/pdf',size:2400000,authorUserId:'u_owner',createdAt:'2026-05-02T10:14:00+02:00',updatedAt:'2026-05-12T14:32:00+02:00',visibility:'Bureau',tags:['Partenariat','Juridique','2026'],version:3,versions:[],favorite:true,eventId:null,blobKey:null},
  {id:'doc2',structureId:'s_lembuscade',folderId:'f2',name:'Budget Summer Closing.xlsx',description:'Budget détaillé confidentiel.',mime:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',size:87000,authorUserId:'u_marie',createdAt:'2026-06-10T10:00:00+02:00',updatedAt:'2026-06-21T16:20:00+02:00',visibility:'Trésorerie',tags:['Budget','2026','confidentiel'],version:2,versions:[],favorite:true,eventId:'e3',blobKey:null},
  {id:'doc3',structureId:'s_lembuscade',folderId:'f3',name:'Checklist rentrée.docx',description:'Checklist opérationnelle.',mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',size:55000,authorUserId:'u_jules',createdAt:'2026-08-20T12:00:00+02:00',updatedAt:'2026-09-06T09:10:00+02:00',visibility:'Staff',tags:['Event','Checklist'],version:1,versions:[],favorite:false,eventId:'e2',blobKey:null},
  {id:'doc4',structureId:'s_lembuscade',folderId:'f4',name:'Visuel rentrée.png',description:'Visuel campagne.',mime:'image/png',size:1200000,authorUserId:'u_sophie',createdAt:'2026-09-08T15:00:00+02:00',updatedAt:'2026-09-11T09:02:00+02:00',visibility:'Staff',tags:['Communication'],version:1,versions:[],favorite:false,eventId:'e2',blobKey:null},
  {id:'doc_other',structureId:'s_autre',folderId:'f_other',name:'budget-ultra-secret.pdf',description:'Ne doit jamais être visible depuis L’Embuscade.',mime:'application/pdf',size:1234,authorUserId:'u_other',createdAt:d(-5),updatedAt:d(-1),visibility:'Privé',tags:['budget','secret'],version:1,versions:[],favorite:false,eventId:null,blobKey:null}
 ],
 albums:[
  {id:'a1',structureId:'s_lembuscade',eventId:'e3',title:'Summer Closing 2026',description:'Les meilleurs moments de la clôture.',status:'PUBLISHED',visibility:'Public',coverMediaId:'med1',createdAt:'2026-06-22T10:00:00+02:00'},
  {id:'a2',structureId:'s_lembuscade',eventId:null,title:'Prépa rentrée',description:'Backstage et préparation.',status:'DRAFT',visibility:'Staff',coverMediaId:null,createdAt:'2026-09-01T10:00:00+02:00'},
  {id:'a_other',structureId:'s_autre',eventId:null,title:'Album secret autre',description:'Cross tenant',status:'PUBLISHED',visibility:'Privé',coverMediaId:null,createdAt:d(-2)}
 ],
 media:[{id:'med1',structureId:'s_lembuscade',albumId:'a1',name:'summer-cover.jpg',mime:'image/jpeg',size:1800000,createdAt:'2026-06-22T10:05:00+02:00',blobKey:null,order:0,visibility:null}],
 folklorePages:[
  {id:'fp1',structureId:'s_lembuscade',slug:'histoire',category:'Histoire',title:'Histoire de L’Embuscade',status:'PUBLISHED',visibility:'Public',authorUserId:'u_emma',updatedAt:'2026-09-01T12:00:00+02:00',version:4,body:'L’Embuscade est née d’une volonté simple : rassembler, transmettre et documenter une culture étudiante vivante. Depuis 2014, chaque mandat enrichit la mémoire de la structure.',versions:[{version:3,title:'Histoire de L’Embuscade',body:'Version précédente de l’histoire.',at:'2026-05-01T12:00:00+02:00'},{version:4,title:'Histoire de L’Embuscade',body:'L’Embuscade est née d’une volonté simple : rassembler, transmettre et documenter une culture étudiante vivante. Depuis 2014, chaque mandat enrichit la mémoire de la structure.',at:'2026-09-01T12:00:00+02:00'}]},
  {id:'fp2',structureId:'s_lembuscade',slug:'glossaire',category:'Glossaire',title:'Glossaire de la guindaille',status:'PUBLISHED',visibility:'Public',authorUserId:'u_sophie',updatedAt:'2026-08-28T14:00:00+02:00',version:2,body:'Un glossaire destiné aux nouveaux étudiants : expressions, usages et références propres à la vie étudiante liégeoise.',versions:[]},
  {id:'fp3',structureId:'s_lembuscade',slug:'traditions-internes',category:'Traditions',title:'Traditions internes',status:'PUBLISHED',visibility:'Membres',authorUserId:'u_owner',updatedAt:'2026-09-10T12:00:00+02:00',version:7,body:'Cette page rassemble les traditions internes validées par la structure et destinées uniquement aux membres.',versions:[]}
 ],
 planningItems:[
  {id:'p1',structureId:'s_lembuscade',title:'Réunion comité',type:'meeting',team:'Bureau',startAt:d(0,18),endAt:d(0,19),assigneeMemberIds:['m1','m2','m5'],status:'TODO',deadline:null},
  {id:'p2',structureId:'s_lembuscade',title:'Préparation tournoi',type:'task',team:'Logistique',startAt:d(1,16),endAt:d(1,18),assigneeMemberIds:['m4','m6'],status:'TODO',deadline:d(1,18)},
  {id:'p3',structureId:'s_lembuscade',title:'Tournoi de fléchettes',type:'event',team:'Événement',startAt:d(1,20),endAt:d(2,1),assigneeMemberIds:['m1','m4','m6'],status:'TODO',deadline:null,eventId:'e1'}
 ],
 accountingEntries:[
  {id:'acc1',structureId:'s_lembuscade',eventId:'e3',type:'REVENUE',category:'Entrées',supplier:null,label:'Entrées Summer Closing',planned:3600,actual:3852,paid:true,status:'VALIDATED',note:'',receiptDocumentId:null,createdAt:'2026-06-21T08:00:00+02:00'},
  {id:'acc2',structureId:'s_lembuscade',eventId:'e3',type:'REVENUE',category:'Bar',supplier:null,label:'Bar Summer Closing',planned:4700,actual:4568,paid:true,status:'VALIDATED',note:'',receiptDocumentId:null,createdAt:'2026-06-21T08:10:00+02:00'},
  {id:'acc3',structureId:'s_lembuscade',eventId:'e3',type:'EXPENSE',category:'Location',supplier:'Salle X',label:'Location salle',planned:1500,actual:1500,paid:true,status:'VALIDATED',note:'',receiptDocumentId:null,createdAt:'2026-06-21T09:00:00+02:00'},
  {id:'acc4',structureId:'s_lembuscade',eventId:'e3',type:'EXPENSE',category:'Boissons',supplier:'Fournisseur Y',label:'Commande boissons',planned:3300,actual:3420,paid:true,status:'VALIDATED',note:'',receiptDocumentId:'doc2',createdAt:'2026-06-21T09:10:00+02:00'},
  {id:'acc5',structureId:'s_lembuscade',eventId:'e3',type:'EXPENSE',category:'Sécurité',supplier:'Sécurité Z',label:'Sécurité',planned:900,actual:900,paid:true,status:'LOCKED',note:'',receiptDocumentId:null,createdAt:'2026-06-21T09:20:00+02:00'}
 ],
 eventStats:[
  {id:'st1',structureId:'s_lembuscade',eventId:'e3',entries:642,scans:615,capacity:700,revenue:8420,cost:5820,estimatedProfit:2300,actualProfit:2600,hourly:[['21:00',45],['22:00',120],['23:00',190],['00:00',140],['01:00',85],['02:00',42],['03:00',20]],entryPoints:[['Entrée principale',420],['Cour',140],['VIP',82]],publicSummary:null},
  {id:'st2',structureId:'s_lembuscade',eventId:'e1',entries:0,scans:0,capacity:220,revenue:0,cost:180,estimatedProfit:-180,actualProfit:null,hourly:[],entryPoints:[],publicSummary:null},
  {id:'st3',structureId:'s_lembuscade',eventId:'e2',entries:0,scans:0,capacity:650,revenue:0,cost:0,estimatedProfit:1200,actualProfit:null,hourly:[],entryPoints:[],publicSummary:null}
 ],
 publicPages:[
  {id:'page1',structureId:'s_lembuscade',status:'PUBLISHED',publishedAt:'2026-08-01T10:00:00+02:00',hiddenAt:null,createdAt:'2026-08-01T09:00:00+02:00',updatedAt:'2026-08-01T10:00:00+02:00'},
  {id:'page_other',structureId:'s_autre',status:'PUBLISHED',publishedAt:'2026-08-15T10:00:00+02:00',hiddenAt:null,createdAt:'2026-08-15T09:00:00+02:00',updatedAt:'2026-08-15T10:00:00+02:00'}
 ],
 structureClaims:[],
 visibilityPolicies:[
  {id:'vp1',structureId:'s_lembuscade',resourceType:'section',resourceId:'presentation',level:'Public'},
  {id:'vp2',structureId:'s_lembuscade',resourceType:'section',resourceId:'members',level:'Public'},
  {id:'vp3',structureId:'s_lembuscade',resourceType:'section',resourceId:'events',level:'Public'},
  {id:'vp4',structureId:'s_lembuscade',resourceType:'section',resourceId:'albums',level:'Public'},
  {id:'vp5',structureId:'s_lembuscade',resourceType:'section',resourceId:'folklore',level:'Public'},
  {id:'vp6',structureId:'s_lembuscade',resourceType:'section',resourceId:'sponsors',level:'Public'},
  {id:'vp7',structureId:'s_lembuscade',resourceType:'section',resourceId:'stats',level:'Privé'},
  {id:'vp8',structureId:'s_lembuscade',resourceType:'section',resourceId:'documents',level:'Bureau'}
 ],
 publicPosts:[
  {id:'post1',structureId:'s_lembuscade',title:'La rentrée approche',body:'Notre calendrier de rentrée est maintenant disponible.',status:'PUBLISHED',publishAt:d(-3,12),eventId:'e2',authorUserId:'u_sophie',image:null,visibility:'Public'},
  {id:'post2',structureId:'s_lembuscade',title:'Tournoi de fléchettes',body:'Rendez-vous demain soir chez Mémé pour notre tournoi de rentrée.',status:'PUBLISHED',publishAt:d(0,12),eventId:'e1',authorUserId:'u_sophie',image:null,visibility:'Public'},
  {id:'post3',structureId:'s_lembuscade',title:'Annonce programmée',body:'Cette annonce ne doit apparaître que demain.',status:'SCHEDULED',publishAt:d(1,12),eventId:null,authorUserId:'u_sophie',image:null,visibility:'Public'}
 ],
 archives:[],auditLogs:[],
 notifications:[
  {id:'n1',structureId:'s_lembuscade',userId:'u_owner',type:'INVITATION_PENDING',title:'2 invitations en attente',read:false,createdAt:d(-1)},
  {id:'n2',structureId:'s_lembuscade',userId:'u_owner',type:'EVENT_SYNC',title:'Le tournoi est prêt à publier dans l’app',read:false,createdAt:d(0,8)}
 ]
};
