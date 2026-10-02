# CyTools PersonaRP sur Google Colab — tâches de voix

Ce dossier est un **projet à part**, fait pour Google Colab et rangé sur votre Google Drive.
Il fait dire des listes de répliques par vos personnages, plusieurs à la fois sur le GPU loué,
et range tout sur Drive. Il ne contient **aucun modèle** : l'outil les télécharge lui-même en
ligne de commande sur Colab, puis ils sont recopiés sur Drive, où l'outil les relit aux
sessions suivantes.

Le SDK CyToolsCore 0.10.1 est public (https://github.com/MrMybal/CyToolsCore, licence MIT) :
l'étape **Installer** le prend sur GitHub, au commit que l'outil fixe dans `app/requirements.txt`.

## Mise en place (une fois)

1. Copiez ce dossier entier dans votre Drive, par exemple `Mon Drive/CyTools_PersonaRP_Colab`.
2. Dans Drive, ouvrez `PersonaRP_Colab.ipynb` avec **Google Colaboratory**.
3. *Exécution › Modifier le type d'exécution* : choisissez un GPU (T4, L4, A100…). Le notebook
   s'adapte à la carte qu'il reçoit.

## Déroulé d'une session

Les cellules du notebook appellent toutes `personarp_colab.py` en ligne de commande :

| Étape | Commande | Durée indicative |
| --- | --- | --- |
| Paramètres | chemin du projet, modèles, licence, précision | — |
| Drive et GPU | monte Drive, affiche la carte | quelques secondes |
| Installer | copie l'outil sur le disque Colab, installe son moteur de voix (PyTorch, Qwen3-TTS) avec l'installeur de l'outil | 3 à 5 min, à chaque session |
| Modèles | `tool.py invoke install_voice_model` : téléchargement par l'outil (révision épinglée, tailles et SHA-256 vérifiés), copie sur Drive vérifiée, puis suppression de la copie locale | la première fois seulement (4,5 Go pour le 1.7B Base) ; ensuite « déjà sur Drive » |
| Essai | une réplique sur cette carte ; choisit la précision (bfloat16 sur A100/L4, float16 sur T4, repli en float32 si la prise n'est pas bonne) | moins d'une minute |
| Tâches | vérifie chaque tâche sans rien générer : qui dit quoi, avec quelle voix, quel modèle manque | quelques secondes |
| Lancer | exécute les tâches | selon la liste |
| État | ce qui est installé, sur Drive, et fait | — |
| Rapport | écrit `resultats/rapport-colab-<date>.json` : la carte, le moteur (PyTorch, CUDA), les modèles sur Drive, et le journal de chaque commande de la session (durée, succès, dernières lignes affichées). Sans jeton, sans modèle, sans voix : c'est le fichier à renvoyer pour faire le point | quelques secondes |

**Licences** : les modèles ne sont téléchargés que si vous avez coché
`J_ACCEPTE_LES_LICENCES` après avoir lu la licence affichée (Qwen3-TTS : Apache-2.0, page du
modèle sur Hugging Face).

## Une tâche

Une tâche est un dossier dans `taches/` :

    taches/
      ma-scene/
        liste.csv            la liste des répliques (ou .txt, .json) — une seule par dossier
        personnages/         les personnages exportés par PersonaRP, avec leurs enregistrements
          valdrenn.zip
        tache.json           facultatif : les réglages de la tâche

**Les personnages** s'exportent depuis PersonaRP sur votre PC : *Bibliothèque › Export et
import*, cochez *Inclure les enregistrements de référence*. Le paquet contient la fiche, le
monde et toutes les voix stables, y compris celles des autres langues. Colab n'a pas de
bibliothèque : une tâche ne parle qu'avec les personnages qu'elle apporte.

**La liste** a les formats de l'onglet Lots de PersonaRP :

- CSV : `id;personnage;texte;langue` (l'`id` nomme la prise : `SC01-05.wav`) ;
- script : `SC01-05 | Maëlis: [ton: bas] Le col est fermé.` — une ligne par réplique ;
- JSON : `[{"id": "SC01-05", "personnage": "Maëlis", "texte": "…", "langue": "English"}]`.

**`tache.json`** (tout est facultatif) :

    {"nom": "ma-scene", "langue": "", "taille_lot": 0, "graine": 42,
     "precision": "", "bibliotheque": false, "appareil": "cuda"}

`langue` vide : chaque personnage dans la sienne. `taille_lot` 0 : taille mesurée sur la carte.
`precision` vide : celle choisie par l'essai.

## Les résultats

Chaque tâche écrit dans `resultats/<nom>-<date>/`, au fur et à mesure :

    personnages/     les personnages que la tâche a apportés
    source.csv       la liste telle que donnée
    lot.json         la tâche telle qu'elle a été comprise
    voix/            un WAV par réplique, nommé d'après son ID
    resultats.json   pour chaque réplique : ID, texte, fichier, durée, voix et langue, ou l'erreur
    resultats.csv    la même chose pour un tableur

`resultats/_taches.json` retient ce qui est fait. Si la session Colab s'arrête ou si vous
interrompez la cellule, relancez simplement **Lancer** : la tâche reprend là où elle en était,
sans refaire ce qui est déjà écrit sur Drive. Une tâche terminée n'est pas refaite ; pour la
refaire, retirez sa ligne de `_taches.json`.

## Plusieurs répliques à la fois

Les répliques sont générées par lots dans une seule copie du modèle. Un premier lot de 4
mesure ce que coûte une réplique sur la carte, les suivants sont dimensionnés d'après la
mémoire libre. Sur une RTX 3090 (24 Go), 16 répliques clonées : 74,7 s une par une, 15,7 s en
lots automatiques. Une réplique clonée coûte environ 1,3 Go pendant sa génération.

## Ce qui a été vérifié, et ce qui ne l'a pas été

Vérifié sur Windows (RTX 3090), le 25 septembre 2026 :

- la fabrication de ce dossier, sans aucun fichier de modèle ;
- l'outil qui démarre sans interface graphique ni bibliothèque audio ;
- `installer` (copie du code, installation légère), `etat`, `taches` : la tâche d'exemple
  signale le modèle manquant et dit quel `--modele` ajouter ; puis, l'outil lisant ses modèles
  dans un autre dossier comme il le fera sur Drive, les 10 répliques sont prêtes ;
- `modeles` sans accord de licence : l'outil refuse avant tout téléchargement, affiche la
  licence et sa source, et le jeton du client n'apparaît ni à l'écran ni dans le projet ;
- la copie vérifiée des modèles (taille et SHA-256, une copie abîmée est détectée) ;
- les adresses et tailles des 66 fichiers du catalogue de voix sur Hugging Face ;
- une réplique en float16, la précision d'une T4 : Whisper y retrouve la phrase exacte, comme
  en bfloat16.

**Rien n'a encore tourné sur Colab lui-même** : ni l'installation du moteur sous Linux, ni
le téléchargement complet d'un modèle par l'outil, ni une tâche sur T4, L4 ou A100. La
première session est donc aussi un test ; chaque étape dit clairement ce qui ne va pas.

## Licence

CyTools PersonaRP: GNU General Public License v3.0 only (`LICENSE`). CyToolsCore 0.10.1, which
the Install step takes from GitHub: MIT (`LICENCES/CyToolsCore-MIT.txt`). Sources of every
component: `LICENCES/SOURCES.txt`. Models keep their own licences and are downloaded separately.
