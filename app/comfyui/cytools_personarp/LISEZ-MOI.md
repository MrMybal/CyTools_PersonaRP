# Nodes CyTools PersonaRP pour ComfyUI

Ces nodes font entrer vos personnages PersonaRP dans ComfyUI : leur apparence pour les modèles
d'image, leurs dialogues avec les prompts image et vidéo de la scène, leur voix, et tout le reste
de l'outil. Ils sont dans la catégorie **CyTools/PersonaRP**.

## Installation

Depuis PersonaRP : **Bibliothèque › ComfyUI**, bouton **Installer ici** à côté de votre ComfyUI
(les installations de Comfy Desktop sont trouvées toutes seules), ou **Installer dans ce dossier**
pour un autre ComfyUI. En ligne de commande, l'opération `install_comfyui_nodes` fait la même
chose. Puis **redémarrez ComfyUI**.

L'installation copie ce dossier dans `custom_nodes/cytools_personarp` et écrit `config.json`,
qui dit où est PersonaRP. Réinstaller remplace la copie ; rien d'autre dans ComfyUI n'est touché.
Pour les retirer, supprimez simplement ce dossier.

## Comment ça marche

Les nodes n'importent jamais PersonaRP : ComfyUI garde son Python, PersonaRP garde le sien, ses
modèles et son moteur de voix. Ils parlent à l'outil par son **API locale** (adresse
`127.0.0.1`, jamais le réseau, avec un jeton). Quand un node s'exécute et que PersonaRP ne répond
pas, ComfyUI le démarre avec son propre Python, puis l'arrête en se fermant. Ouvrir ComfyUI ne
démarre rien : les menus (personnages, voix, modèles) sont lus dans les fichiers de l'outil
tant qu'il ne tourne pas.

Le jeton est créé par PersonaRP et rangé dans son dossier `data/settings` : il n'apparaît dans
aucun workflow ni aucun widget.

La barre de progression de ComfyUI suit le travail de l'outil, et le bouton **Stop** l'annule.

## La mémoire graphique

Une carte de 24 Go ne tient pas à la fois un modèle d'image, un modèle de langage et un modèle
de voix. Les nodes qui utilisent le GPU ont deux réglages, activés par défaut :

- **liberer_vram_comfyui** : décharge les modèles de ComfyUI avant de demander le travail ;
- **rendre_la_vram_apres** : demande à PersonaRP de libérer ses modèles une fois fini.

Désactivez-les pour enchaîner plusieurs nodes PersonaRP sans recharger les modèles.

## Les nodes

| Node | Entrées | Sorties |
| --- | --- | --- |
| **Personnage** | un personnage | persona_id, nom, apparence, étiquettes visuelles (prêtes pour un prompt), fiche JSON |
| **Dialogue** | personnage, message, scène (nouvelle, continuer la dernière, continuer une scène donnée, sans mémoire), directive de scène, parler, modèle, appareil, seed | réponse, texte parlé, prompt image, prompt vidéo, prompt négatif, directive JSON, audio, session_id |
| **Voix** | personnage, texte, langue (la configuration de voix par langue de la fiche s'applique), voix stable, seed, appareil | audio, fichier (copié dans `output/personarp`), durée, voix utilisée |
| **Prompts de scène** | directive JSON (celle du Dialogue), personnage | prompt image, prompt vidéo, prompt négatif, résumé |
| **Traduire** | texte, langue cible, langue source, modèle, personnage et note de contexte facultatifs, session facultative | traduction (les marques de jeu `[ton: …]` restent en place), modèle utilisé |
| **Lire une photo** | image, langue, modèle de vision | apparence, étiquettes visuelles, proposition JSON, modèle utilisé, observation (la description détaillée en anglais dont la fiche est tirée) |
| **Tâche de voix** | liste (script `ID \| Nom: texte`, CSV ou JSON), nom, langue, taille de lot, précision, paquets de personnages (un chemin par ligne), vérifier seulement | dossier de la tâche, résumé, résultats JSON, toutes les prises enchaînées en un audio |
| **Opération PersonaRP (avancé)** | n'importe quelle opération de l'outil, paramètres JSON | résultat JSON |

Les sorties AUDIO se branchent sur les nodes audio de ComfyUI (Save Audio, Preview Audio…), les
sorties texte sur n'importe quel encodeur de prompt.

**Donner du contexte à la traduction.** Une phrase isolée est ambiguë : sans contexte, « le
col » a été rendu par « the gate » et « the collar ». Choisissez un **personnage** : son monde
(lieux, termes, ton), sa façon de parler et sa scène en cours accompagnent la demande. Reliez une
**session_id** pour y ajouter les répliques qui précèdent, et écrivez dans **contexte** ce qu'ils
ne disent pas (« au pied d'un col enneigé »). Rien de ce contexte n'est traduit. Avec « (celui de
la fiche) » et sans personnage, c'est le modèle de l'assistant qui traduit — souvent un modèle
de jeu de rôle ; la sortie `modele_utilise` dit qui a traduit.

## Réglages

`config.json` : `tool_root` (le dossier de PersonaRP), `port` (8791 par défaut), `auto_start`.
La variable d'environnement `PERSONARP_TOOL_ROOT` remplace `tool_root`.

Journal du serveur démarré par ComfyUI : `data/logs/comfyui-server.log` dans PersonaRP.

## Licence

GNU GPL version 3 (GPL-3.0-only), comme CyTools PersonaRP : voir `LICENSE` dans ce dossier.
