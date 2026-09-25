# CyTools PersonaRP — 0.1.0

Lancer **CyTools_PersonaRP.exe**. La fenêtre s'ouvre directement : pas de terminal, pas de
JSON à écrire.

**Aucun modèle n'est fourni avec l'outil.** Les moteurs et les modèles se téléchargent depuis
l'interface, chacun avec sa licence à accepter : voir *Premier lancement* ci-dessous.
PersonaRP garde ses propres copies et ne dépend d'aucun autre outil.

## Premier lancement

1. Onglet **Modèles** : installer le moteur de conversation (**CUDA** pour une carte NVIDIA,
   sinon **CPU**), puis au moins un modèle de conversation. Les fiches d'exemple sont réglées
   sur *Nymphaea RP 4B* ; tout autre modèle installé se choisit sur la fiche, onglet Modèle.
2. Onglet **Voix** : installer le moteur de parole (environ 8 Go), puis les modèles de parole
   utiles — **1.7B Base** pour les voix stables, **1.7B VoiceDesign** pour inventer une voix,
   **1.7B CustomVoice** pour les voix prédéfinies, **Whisper** pour transcrire les prises.
3. Facultatif, onglet **Modèles** : un modèle de **vision** (Qwen2.5-VL 7B) pour lire les photos
   de personnage.

Chaque téléchargement s'annule et se reprend, et n'est déclaré installé qu'une fois son
SHA-256 vérifié.

## Ce que fait l'outil

Créer des personnages **persistants**, les faire vivre dans un **monde partagé**, jouer des
scènes avec eux, et récupérer pour chaque réplique une **description exploitable** de ce
qu'une caméra verrait.

- **Personnages** — une fiche complète : identité, apparence, personnalité, façon de parler,
  passé, état du moment, mémoire, relations, voix, direction visuelle et réglages du modèle.
  Chaque enregistrement crée une révision ; l'ancienne est conservée et restaurable.
- **Mondes** — le lore partagé : lieux, factions, lois, chronologie, glossaire, ce qui doit
  rester vrai et ce qui n'arrive jamais. Plusieurs personnages peuvent partager un monde ;
  chacun sait alors qui d'autre y vit.
- **Relations** — qui est qui l'un pour l'autre, avec un sentiment, une confiance, une
  histoire commune, une tension et ce qu'on lui cache. Le lien inverse peut être écrit
  automatiquement sur l'autre fiche.
- **Scènes** — une conversation sauvegardée par personnage, reprise plus tard telle quelle.
- **Mémoire** — explicite. Rien n'est extrait d'une conversation sans que vous l'ajoutiez.
- **Assistant** — pour faire écrire une fiche, un monde, ou une seule section. La proposition
  est relue et modifiable ; elle n'est appliquée que si vous le demandez.
- **Voix stable** — une prise de 12 à 24 secondes capturée une fois, puis clonée pour toutes
  les répliques suivantes, avec des annotations de jeu écrites par le personnage lui-même.
- **Import / export** — un personnage s'exporte avec son monde et sa fiche de voix, en un
  seul fichier transportable.

## Mondes d'exemple

Six mondes prêts à jouer sont fournis, chacun avec trois ou quatre personnages complets, leurs
relations et un secret à découvrir : une **fantasy épique** dans l'esprit des grandes sagas
(entièrement originale), une **science-fiction** de station spatiale, un **cyberpunk**
marseillais, une **horreur gothique** normande, un **post-apocalyptique** de caravanes et une
**fantasy douce** dans l'esprit des Archives Flottantes.

Onglet **Bibliothèque › Exemples**, bouton **Importer ce monde**. L'import est une copie :
l'exemple ne change jamais et un personnage existant n'est jamais écrasé. Les fichiers sont
dans `app/examples`, avec leur présentation dans `app/examples/LISEZ-MOI.md`. Chaque
personnage arrive avec sa **voix stable** : on peut jouer et entendre une scène dès l'import.

## Les descriptions d'image, de vidéo et de mouvement

Dans la fiche, onglet **Direction visuelle**, activer « Décrire le plan à chaque réponse ».
À chaque réplique, l'outil produit en plus du dialogue un objet JSON structuré : allure,
pose, expression, action, **suite de mouvements horodatés**, cadrage, décor, lumière, plus
un prompt image et un prompt vidéo déjà rédigés.

Ce bloc apparaît dans la conversation, replié sous la réplique, et il est copiable. **Il
n'est jamais lu à voix haute** : c'est de la donnée, pas du dialogue. L'outil décrit, il ne
fabrique ni image ni vidéo — le prompt est fait pour être porté vers un outil de rendu.

Par défaut la description est produite par une **seconde passe contrainte** : le modèle de
jeu écrit la réplique, puis une passe séparée décrit le plan avec une grammaire qui garantit
un JSON valide. C'est pour cette raison que la description ne déborde jamais dans le
dialogue. Un petit modèle de roleplay remplit la structure mais reste pauvre ; on peut
choisir un modèle plus gros pour la description seule, sans changer celui qui joue.

Les « cibles supplémentaires » permettent de demander en plus une forme attendue par un
outil précis : donner son nom, et le descripteur remplit une entrée à part pour lui.

## Les photos de personnage

Dans la fiche, onglet **Apparence**, vous pouvez attacher des photographies : un portrait,
un plan en pied, une tenue, un détail, une expression, un décor. Elles sont **copiées à côté
du personnage**, elles partent avec un export, et l'outil signale si l'une d'elles a été
déplacée ou modifiée depuis son ajout. Le modèle de jeu ne les voit jamais : il ne lit que
du texte.

### Extraire la description visuelle

Bouton **Décrire le personnage à partir de cette photo**. Un modèle de vision lit l'image en
**deux temps**. Il **regarde** d'abord : il décrit la personne en prose détaillée (visage, peau,
cheveux, yeux, expression, chaque vêtement avec sa couleur, sa matière et ses motifs, bijoux,
sacs, marques), là où ces modèles sont le plus précis. Puis il **rédige** la branche Apparence
à partir de ce qu'il a vu : résumé, carrure, visage, cheveux, yeux, peau, tenue, marques,
accessoires, âge apparent — des phrases, pas des mots isolés — et surtout les **tags
visuels**. Un champ que la photo ne montre pas (la carrure sur un portrait) reste vide plutôt
qu'inventé ; ce qui glisse d'une autre langue ou d'un autre alphabet est retiré.

Ces tags sont le point important. Ce sont six à douze groupes de mots, du genre
« cheveux noirs relevés », « kimono bleu nuit à étoiles brodées », « sac de cuir brun », qui
sont ensuite **repris mot pour mot dans chaque prompt d'image** du personnage. C'est ce qui
fait qu'il reste reconnaissable d'un plan à l'autre. La grammaire de décodage interdit les
tags trop courts : « femme », « bleue » ou « yeux bleus » n'identifient personne.

Le résultat est une **proposition**, pas une écriture directe : vous la relisez dans
l'onglet Assistant et vous l'appliquez si elle vous convient. Elle ne remplace que la
branche Apparence ; la mémoire, le passé et les relations ne sont pas touchés. Le modèle a
pour consigne de ne décrire que ce qui est visible, et de ne jamais inventer un nom ou une
histoire à partir d'une image.

Le modèle de vision (Qwen2.5-VL 7B, 6 Go) s'installe depuis l'onglet **Modèles**, comme les
autres, avec acceptation de licence. Compter une vingtaine de secondes par photo sur GPU
(les deux temps compris).

## La voix

La voix compte autant que le texte : c'est elle qui rend un dialogue jouable. Onglet **Voix**.

### Créer une voix stable

C'est le cœur du dispositif, en trois gestes.

1. **Capturer une prise** de 12 à 24 secondes. Soit vous **décrivez** la voix en une phrase
   (« femme, fin de vingtaine, grave et posée, débit lent, chaleur contenue ») et elle est
   inventée ; soit vous choisissez une **voix prédéfinie** ; soit vous fournissez votre
   **propre enregistrement**. La prise est transcrite automatiquement, parce qu'un clonage a
   besoin des mots réellement prononcés, pas de ceux que vous vouliez.
2. **Écouter.** La durée est affichée et l'outil dit si elle est dans la bonne fenêtre.
3. **Garder.** La prise devient une voix stable : verrouillée, empreinte enregistrée,
   rattachée au personnage. **Toutes ses répliques suivantes sont clonées depuis cette
   prise**, donc la voix ne dérive plus d'une réplique à l'autre ni d'une session à l'autre.

La prise est conservée à côté de la bibliothèque, pas dans le dossier temporaire du job :
vous pouvez la reprendre demain. **Vérifier** signale si l'enregistrement de référence a été
déplacé ou modifié, plutôt que de produire une voix qui ne ressemble plus à rien.

### Le jeu vocal

Le personnage peut écrire ses propres indications dans ses répliques : `[ton: sourd]`,
`[pause: 400ms]`, `[émotion: soulagement]`, `[rythme: lent]`, `[murmure]`, `[emphase: jamais]`
— en français comme en anglais. Un ton reste actif jusqu'à ce qu'il soit changé ou remis à
`normal` ; une emphase ne vaut que pour son passage. Les pauses deviennent de vrais silences
à la bonne durée. **Rien de tout cela n'est prononcé.**

Ne sont pas lus non plus : les didascalies entre astérisques (réglable) et la description de
scène, jamais.

Par défaut, la façon de dire est dérivée de la fiche — personnalité, style de parole,
registre, humeur du moment — et de la réplique à laquelle le personnage répond. La mémoire et
le lore ne sont pas injectés dans la consigne vocale : ce ne sont pas des éléments de jeu.

Une limite à connaître : **une voix clonée ne lit aucune consigne écrite**. Le modèle de
clonage de Qwen3-TTS reproduit sa prise et n'a pas d'entrée pour une direction ; les
indications `[ton: …]`, `[émotion: …]` et la direction permanente ne guident donc que les voix
inventées et les voix prédéfinies. Les **pauses**, elles, s'appliquent à toutes les voix.

### Traduire une scène et l'entendre dans une autre langue

Une scène s'écrit dans la langue du personnage. Ensuite, dans l'onglet **Scène**, le bandeau
**Traduction et voix dans d'autres langues** :

1. choisissez la **langue** et le **modèle de traduction** — n'importe quel modèle installé,
   pas forcément celui qui joue le personnage ;
2. **Traduire la scène**. La traduction est rangée **à côté** de chaque réplique : l'original
   n'est jamais modifié, et une scène peut porter plusieurs langues. Les répliques déjà
   traduites ne sont pas renvoyées au modèle ; **Tout retraduire** force une nouvelle passe.
   Les indications de jeu (`[ton: …]`, `[pause: …]`) sont masquées avant la traduction et
   remises en place après : le modèle ne peut ni les traduire ni en inventer. S'il en perd
   une, c'est affiché sous la réplique.
   **Chaque demande porte le contexte de la scène**, que le modèle lit sans le traduire : le
   monde (genre, ton, cadre, et d'abord les lieux, factions et termes du glossaire que les
   répliques mentionnent), la façon de parler du personnage, où en est la scène (lieu, moment,
   humeur) et les répliques qui précèdent, dans leurs mots d'origine — même quand on ne
   traduit qu'une réplique. Une **précision pour le traducteur** s'ajoute dans le bandeau. Un
   mot ambigu prend ainsi le sens qu'il a ici : isolée, « Le col est fermé » est devenue « the
   gate » ; dans sa scène, « the pass ».

   **Les termes du monde gardent la même traduction partout.** La première fois qu'une scène
   mentionne le monde, un lieu, une faction ou un terme du glossaire, il est traduit une seule fois et
   rangé dans le monde, avec sa langue ; toutes les traductions suivantes, dans toutes les
   scènes, doivent l'employer tel quel (« Roi-Cendre » reste « the Ash-King »). Une réplique
   qui l'oublie est redemandée une fois ; ce qui manque encore est signalé sous la réplique.
   Un mot ordinaire qui s'écrit comme un terme (« nommer » les morts, quand le glossaire a
   « Nommer ») reste un mot ordinaire ; un terme est reconnu même quand le français contracte
   son article (« aux Archives Flottantes », « du Pont des Brumes »). Le lexique se lit et se
   corrige dans l'onglet
   **Mondes › Traduction des termes** : ce que vous écrivez là n'est jamais remplacé, et il
   voyage avec le monde dans les exports.
3. **Dire en anglais** (ou la langue choisie) sur chaque réplique. La prise est gardée avec la
   scène (`data/sessions/<personnage>/audio/`) et se réécoute sans être refaite.

**La voix de chaque langue se configure sur la fiche**, onglet Personnages › Voix › *Autres
langues*. Pour chaque langue, vous choisissez :

- **La même voix, en gardant l'accent** — le personnage parle anglais avec sa voix et son
  accent français. C'est ce qui se passe pour une langue que vous n'avez pas configurée.
- **La même voix, prononciation native** — seul le timbre est repris de la prise ; les mots
  sont prononcés comme le modèle prononce cette langue.
- **Une autre voix stable** — une vraie voix anglaise pour l'anglais. Capturez-la dans l'onglet
  Voix avec **Langue de la prise : Anglais**, décrivez un locuteur natif, puis **La garder comme
  : sa voix en anglais seulement**. La voix principale du personnage n'est pas touchée. Un
  enregistrement importé peut aussi servir.
- **Une voix inventée** ou **une voix prédéfinie**, avec une direction propre à la langue.

Chaque langue peut aussi avoir sa graine. Le banc d'essai de l'onglet Voix a un choix de
**langue parlée** : vous entendez ce que la fiche produira sans jouer de scène, et la ligne sous
le choix dit quelle voix sera utilisée.

### Faire dire toute une liste de répliques : les tâches de l'onglet Lots

L'onglet **Lots** lance des **tâches**. Une tâche fait dire d'un seul coup une liste de
répliques — qui dit quoi — et range tout dans son propre dossier. Les répliques ne passent pas
une par une : elles sont générées **plusieurs à la fois dans une seule copie du modèle de
voix**, autant que la mémoire graphique libre en contient. Une grosse carte louée à l'heure est
donc exploitée à fond au lieu d'attendre réplique après réplique.

**Une tâche peut apporter ses propres personnages.** Section *Personnages de la tâche* :
ajoutez un ou plusieurs paquets exportés par PersonaRP (Bibliothèque › Export et import, case
*Inclure les enregistrements de référence*). Un paquet contient le personnage complet : la
fiche, son monde et **toutes ses voix stables, y compris celles des autres langues**. Ils sont
copiés dans le dossier de la tâche, **jamais dans votre bibliothèque**, et ils sont cherchés
avant elle. Décochez *Chercher aussi dans ma bibliothèque* pour qu'une tâche ne parle qu'avec ce
qu'elle apporte — c'est le cas d'une machine louée qui n'a rien d'autre. Une voix dont
l'enregistrement ne correspond plus à son empreinte est écartée et signalée, jamais utilisée
comme si c'était la même.

La liste se donne de trois façons :

- **un script**, une ligne par réplique : `Maëlis: Le col est fermé.`, ou
  `COL-01 | Maëlis: Le col est fermé.` pour donner son **ID** à la réplique. Une ligne sans nom
  continue la réplique précédente, une ligne qui commence par `#` est un commentaire, et les
  indications de jeu (`[ton: …]`, `[pause: 400ms]`) sont gardées ;
- **un CSV** (séparateur `;`, `,` ou tabulation) avec une ligne d'en-tête : `personnage`,
  `texte`, et au choix `id`, `voix`, `langue`, `fichier`. Sans en-tête : personnage, texte,
  langue, fichier ;
- **un JSON** : une liste d'objets avec les mêmes champs, ou `{"lignes": [...]}`.

**Chaque réplique a un ID** : le sien, ou son numéro (`0007`) si la liste n'en donne pas. Sa
prise porte ce nom (`COL-01.wav`) et l'ID est dans les résultats. Deux répliques ne peuvent pas
avoir le même ID : la seconde est signalée au lieu d'écraser la première.

Un personnage est retrouvé par son identifiant, son nom, un alias, ou un morceau de nom que lui
seul porte (« Vasric » trouve « Sire Vasric d'Aubrecourt »). Si deux personnages
correspondent, la réplique est signalée au lieu d'être donnée au hasard à l'un d'eux. La
colonne `voix` désigne une voix stable, à la place d'un personnage ou en plus de lui. Une
réplique sans langue prend celle de la tâche ; une tâche sans langue fait parler chaque
personnage dans la sienne. Dans une autre langue, c'est la configuration de voix par langue de
la fiche qui décide : sa vraie voix anglaise pour l'anglais si elle en a une, sinon sa voix
avec son accent.

Dans l'onglet :

1. choisissez le fichier (**Parcourir**) ou tapez le script, puis la langue, la carte et la
   taille des lots — **Adapter à la mémoire graphique libre** est coché par défaut ;
2. ajoutez si besoin les **personnages de la tâche** ;
3. **Vérifier la tâche** : un tableau dit, pour chaque réplique, son ID, quel personnage parle
   et d'où il vient (tâche ou bibliothèque), avec quelle voix et dans quelle langue, ou pourquoi
   elle ne peut pas être dite. Rien n'est généré et la carte graphique n'est pas utilisée :
   vérifiez avant de payer ;
4. **Lancer la tâche**. Si une tâche tourne déjà, le bouton devient **Mettre la tâche en
   file** : les tâches passent l'une après l'autre, et la liste dit combien attendent. Une
   réplique impossible (personnage inconnu, voix absente) est notée et le reste continue.

Chaque tâche a son dossier dans `data/batches/<nom>-<date>/` :

    personnages/          les personnages que la tâche a apportés : fiches/, mondes/,
                          voix-stables/ (chaque voix avec son enregistrement), import.json
    source.txt|csv|json   la liste telle que vous l'avez donnée, intacte
    lot.json              la tâche telle qu'elle a été comprise : chaque réplique, son ID, qui la dit
    voix/                 un WAV par réplique, nommé d'après son ID (COL-01.wav, 0007-….wav)
    resultats.json        ce qui est arrivé à chaque réplique : ID, texte, fichier, durée, voix
                          et langue utilisées, ou l'erreur
    resultats.csv         la même chose, pour un tableur

Les résultats sont écrits au fur et à mesure. Une tâche interrompue se **reprend** (liste des
tâches, **Reprendre**) sans refaire les répliques déjà écrites, avec les personnages qu'elle
avait apportés : sur une machine payée à l'heure, rien n'est payé deux fois. **Vérifier ce qui
reste** montre ce que la reprise va faire.

La taille automatique est **mesurée, pas devinée** : un premier lot de 4 répliques — les plus
longues, donc les plus chères — mesure ce que coûte vraiment une réplique sur cette carte, et
les lots suivants sont dimensionnés d'après la mémoire qui reste (32 au plus). Le worker se
limite à la mémoire graphique libre au départ : sous Windows, une carte pleine ne renvoie pas
d'erreur mais déborde en silence dans la RAM, ce qui rend tout très lent ; avec cette limite,
un lot trop gros devient une erreur, il est coupé en deux et relancé. Les répliques de longueur
voisine sont groupées ensemble pour limiter le gaspillage.

Mesuré sur une RTX 3090 (24 Go), 16 répliques clonées, environ 64 s d'audio : une par une
76,5 s, par 4 26,4 s, par 8 16,0 s, en automatique 15,8 s — **4,8 fois plus vite**. Une
réplique clonée coûte environ 1,3 Go pendant sa génération. Pour mesurer une autre carte :
`runtime/python/Scripts/python.exe app/tests/benchmark_batch.py`. Des lots d'exemple, prêts à essayer après l'import du monde Valdrenn,
sont dans `app/examples/lots`.

Une IA branchée en MCP envoie sa liste directement, sans fichier : opération `speak_batch`
avec `text` (script, CSV ou JSON) ou `items`, et `dry_run` pour vérifier d'abord ; plusieurs
tâches envoyées à la suite attendent leur tour. Tout ce qui se lit sur le disque — une liste
en fichier ou des paquets de personnages — passe par `speak_batch_file` (`file`, `personas`,
`use_library`), réservé comme l'import aux clients qui ont la permission `filesystemExternal`.

### PersonaRP dans ComfyUI

L'onglet **Bibliothèque › ComfyUI** installe une bibliothèque de **nodes ComfyUI** qui utilisent
l'outil : **Installer ici** à côté de votre ComfyUI (les installations de Comfy Desktop sont
trouvées toutes seules), ou **Installer dans ce dossier** pour un autre, puis redémarrez
ComfyUI. Ils sont dans la catégorie **CyTools/PersonaRP** :

- **Personnage** — l'apparence et les étiquettes visuelles, prêtes pour un prompt d'image ;
- **Dialogue** — la réponse du personnage, avec les prompts image, vidéo et négatif de la scène,
  la directive en JSON, l'audio si le personnage parle, et la session pour continuer ;
- **Voix** — un texte dit avec la voix du personnage, dans sa langue ou une autre (la
  configuration de voix par langue s'applique), en sortie AUDIO de ComfyUI ;
- **Prompts de scène**, **Traduire**, **Lire une photo**, **Tâche de voix** ;
- **Opération PersonaRP (avancé)** — n'importe quelle opération de l'outil, paramètres en JSON.

Les nodes n'importent jamais l'outil : ComfyUI garde son Python, PersonaRP le sien. Ils passent
par l'API locale de PersonaRP (sur `127.0.0.1` seulement, avec un jeton rangé dans
`data/settings`, jamais dans un workflow). Ouvrir ComfyUI ne démarre rien ; le premier node
exécuté démarre PersonaRP, et fermer ComfyUI l'arrête. La barre de progression de ComfyUI suit
le travail, et **Stop** l'annule. Les nodes qui utilisent le GPU déchargent d'abord les modèles
de ComfyUI et rendent ensuite la mémoire de PersonaRP (deux réglages, activés par défaut).
Mode d'emploi détaillé : `app/comfyui/cytools_personarp/LISEZ-MOI.md`.

### Les tâches sur Google Colab

Pour faire tourner des tâches sur un GPU loué, un **projet Colab à part** se fabrique avec
`runtime/python/Scripts/python.exe app/build_colab.py` : il arrive dans
`..\CyTools_PersonaRP_Colab`, prêt à copier sur Google Drive, avec son notebook. Il ne contient
**aucun modèle** : sur Colab, l'outil les télécharge lui-même en ligne de commande, ils sont
recopiés et vérifiés sur Drive, et l'outil les relit ensuite depuis Drive. Les résultats sont
écrits sur Drive au fur et à mesure, et une tâche coupée reprend où elle en était. Tout est
expliqué dans le `LISEZ-MOI.md` de ce projet.

L'outil sait lire ses modèles et écrire ses tâches ailleurs que dans `data/` : variables
d'environnement `PERSONARP_MODELS_DIR` et `PERSONARP_BATCHES_DIR` (chemins absolus). Les
tâches ont aussi un réglage de **précision** : `auto` prend bfloat16 sur les cartes qui le
calculent (RTX 30/40, A100, L4) et float16 sur les plus anciennes (T4).

### Moteur et modèles

Le moteur de parole est **privé à cet outil** (environ 8 Go) et s'installe depuis l'onglet
Voix, comme les cinq variantes Qwen3-TTS et Whisper large-v3 turbo. Chaque capacité a
ses propres poids : le clonage demande une variante **Base**, une voix prédéfinie demande
**CustomVoice**, une voix inventée demande **VoiceDesign**. L'outil choisit tout seul et vous
prévient s'il doit remplacer.

La transcription sert aussi à dicter : `transcribe` sur un WAV rend le texte. La capture
depuis un micro physique n'est pas dans cette version.

## Langue de l'interface

L'interface est en anglais par défaut et entièrement en français si vous le choisissez dans
**Options**. Seuls les messages renvoyés par une opération elle-même — une erreur du moteur
par exemple — restent en anglais, parce qu'ils sont partagés avec la CLI et MCP.

## Modèles

Onglet **Modèles** : état d'installation, taille, octets déjà présents, licence, source et
révision épinglée pour chaque modèle. La licence s'accepte personnellement avant tout
téléchargement. Un téléchargement s'annule et se reprend ; rien n'est déclaré installé tant
que son SHA-256 ne correspond pas. Les poids vivent dans `data/models/llm`.

Treize modèles sont au catalogue, dont deux de vision ; aucun n'est fourni avec l'outil. Le
choix du modèle, CPU ou GPU NVIDIA, se fait sur la fiche du personnage, onglet **Modèle**. Les
modèles de parole ont leur propre liste dans l'onglet **Voix**.

## Licence

CyTools PersonaRP est un logiciel libre sous **GNU GPL version 3** (GPL-3.0-only), comme le SDK
CyToolsCore sur lequel il repose : le texte complet est dans `LICENSE`. Cela couvre tout
l'outil — le code, l'interface, les nodes ComfyUI, le projet Colab et les mondes d'exemple.
Les modèles (Qwen3, Qwen3-TTS, Whisper…) ne font pas partie de l'outil : ils se téléchargent à
part et gardent chacun leur licence, affichée dans l'onglet Modèles et dans **Options**.

## Mises à jour

Le dépôt de l'outil est **https://github.com/MrMybal/CyTools_PersonaRP**. Il est inscrit dans
`app/release.json`, qui voyage avec l'application : l'onglet **Mises à jour** et l'opération
`update` l'utilisent d'office (on peut en indiquer un autre dans l'onglet). L'application, le
moteur et les poids sont trois flux distincts ; `data/` n'est jamais remplacé, une mise à jour
est vérifiée avant d'être activée au lancement suivant, et la version précédente est gardée
pour revenir en arrière.

Pour qu'une mise à jour soit visible, le dépôt doit être **public** (l'outil lit GitHub sans
identifiant) et porter une **release** dont l'étiquette est la version de l'outil (`v0.2.0`
pour la version `0.2.0`), avec un fichier `cytools-app.zip` contenant le dossier `app/`. Tant
que le dépôt est privé ou sans release, l'onglet le dit en clair.

## Où sont les choses

    CyTools_PersonaRP.exe    le lanceur Windows
    CyTools_PersonaRP.sh     le lanceur Linux (fourni, jamais exécuté)
    app/                     code, manifeste, interface, tests, documentation
    app/examples             les mondes d'exemple, prêts à importer
    app/examples/lots        des lots de répliques d'exemple (script, CSV, JSON)
    app/comfyui              les nodes ComfyUI (copiés dans ComfyUI par l'onglet Bibliothèque › ComfyUI)
    data/personas            vos personnages, avec leurs révisions
    data/worlds              vos mondes
    data/sessions            vos scènes
    data/exports             vos exports
    data/models/llm          les modèles de conversation
    data/models/tts          les modèles de parole
    data/models/stt          les modèles de transcription
    data/voices              vos voix stables et leurs prises
    data/batches             vos lots de voix : la liste, les WAV et les résultats
    data/reports             les preuves, dont VALIDATION.md
    runtime/                 le Python privé, les moteurs et les mises à jour préparées

Rien n'est jamais supprimé par l'outil : « Mettre à la corbeille » déplace vers un
sous-dossier `.trash` que vous pouvez rouvrir.

## Ce qui a été réellement vérifié

Sur Windows 10 x64 avec une carte NVIDIA de 24 Go, ont réellement tourné : la génération sur
GPU, la directive de scène, la
persistance multi-tours, la synthèse vocale, une voix inventée puis figée en voix stable, le
clonage, la transcription, la fenêtre, le lanceur, la CLI et une vraie session MCP, ainsi que
la traduction d'une scène et sa voix en anglais des trois façons (même voix avec accent, même
timbre en prononciation native, vraie voix anglaise propre à l'anglais). Pour les **tâches de
l'onglet Lots**, a tourné sur le vrai modèle une tâche complète : des personnages exportés avec
leurs voix (dont une vraie voix anglaise créée pour l'occasion), importés dans une tâche sur une
bibliothèque vide, 16 répliques en français et en anglais nommées par leur ID — 15,7 s en lots
automatiques contre 74,7 s une par une —, la voix inventée et la voix prédéfinie, la reprise, et
Whisper a confirmé que chaque prise vérifiée dit sa propre réplique. Détails :
`data/reports/VALIDATION.md`. N'ont **pas** été testés : les tâches sur une autre carte (A100)
ou sous Linux, les lots sur processeur, Linux, une vraie release GitHub, un installeur redistribuable, le
téléchargement depuis zéro des modèles de conversation et de parole (seul le modèle de vision
l'a été), la reprise d'un téléchargement interrompu, la capture micro et le mode CPU pour la
parole.

Documentation technique : `app/README.md`.
