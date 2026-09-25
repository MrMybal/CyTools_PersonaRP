"""Build CyTools_PersonaRP_Colab: the project to put on Google Drive and run from Colab.

    python app/build_colab.py [target]

The target defaults to a folder beside the Tool (..\\CyTools_PersonaRP_Colab). It receives the
Tool's code without its window, the runner (colab/personarp_colab.py),
the notebook generated below, its LISEZ-MOI and an example task. No model, ever: the weights
are downloaded on Colab by the Tool itself. Building again replaces the code (outil/) and the
runner, notebook and LISEZ-MOI; the tasks, models and results already in the target are left
alone.
"""
import json
import shutil
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
DEFAULT_TARGET = ROOT.parent / 'CyTools_PersonaRP_Colab'

# What the Colab project leaves out of app/: the desktop window, the developer material, and
# anything that only exists on the machine that builds it.
EXCLUDED = {'gui', 'tests', 'Docs', 'packages', 'colab', 'comfyui', 'locales', '__pycache__',
            'desktop.py', 'advanced_ui.py', 'model_options_ui.py', 'ui_common.py',
            'launcher.cpp', 'build_launcher.cmd', 'build_launcher.ps1', 'dev_launch.cmd',
            'build_colab.py', 'build_example_voices.py', 'build_tts_catalog.py',
            'CyToolsGuide.md', 'AGENTS.md'}

EXAMPLE_LIST = """id;personnage;texte;langue
COL-01;Maëlis;[ton: bas] Le col est fermé depuis trois jours. Personne ne monte plus.;
COL-02;Brannoc;Alors on passera par la rivière. Elle est gelée, ça porte.;
COL-03;Ilyenne;[pause: 400ms] La glace porte ceux que la rivière veut bien porter.;
COL-04;Vasric;Personne ne passe sans mon accord, et je ne l'ai donné à personne.;
COL-05;Maëlis;Tu crois que la glace tiendra sous les chevaux ?;
COL-06;Brannoc;[soupir] Elle a tenu l'hiver dernier. Elle tiendra encore un soir.;
COL-07;Vasric;À l'aube, la herse sera levée. Pas avant.;
COL-08;Ilyenne;Je garderai la chandelle allumée, pour ceux qui reviennent.;
COL-09;Maëlis;The pass has been closed for three days. Nobody goes up any more.;English
COL-10;Brannoc;Then we cross by the river. It is frozen, it will hold.;English
"""
EXAMPLE_SETTINGS = {'nom': 'exemple-valdrenn', 'langue': '', 'taille_lot': 0, 'graine': 42,
                    'precision': '', 'bibliotheque': False}


def markdown(text):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': text.strip('\n').splitlines(True)}


def code(text, title=''):
    metadata = {'cellView': 'form'} if title else {}
    return {'cell_type': 'code', 'execution_count': None, 'metadata': metadata, 'outputs': [],
            'source': text.strip('\n').splitlines(True)}


RUNNER = '!python "{PROJET}/personarp_colab.py" --projet "{PROJET}"'


def notebook():
    cells = [
        markdown("""
# CyTools PersonaRP sur Colab — tâches de voix

Fait dire des listes de répliques par vos personnages, **plusieurs à la fois** sur le GPU de
cette session, et range tout sur **Google Drive**. Le projet ne contient aucun modèle :
**l'outil les télécharge lui-même** (ligne de commande), ils sont recopiés sur Drive et relus
depuis Drive aux sessions suivantes.

Dans le dossier du projet sur Drive :

- `taches/` — une tâche par dossier : sa liste (`.csv`, `.txt` ou `.json`), ses personnages
  exportés par PersonaRP dans `personnages/`, et au besoin `tache.json` ;
- `modeles/` — les poids, remplis par l'étape **Modèles** ;
- `resultats/` — un dossier par tâche : les voix nommées par ID, `resultats.csv`, etc.

Choisissez un GPU (*Exécution › Modifier le type d'exécution*), puis exécutez les cellules
dans l'ordre. Tout est expliqué dans `LISEZ-MOI.md`.
"""),
        code("""
#@title 1. Paramètres
#@markdown Dossier du projet sur votre Drive :
PROJET = '/content/drive/MyDrive/CyTools_PersonaRP_Colab'  #@param {type:"string"}
#@markdown Modèles de voix à installer, séparés par des virgules. Le clonage des voix stables
#@markdown demande `qwen3tts-1.7b-base` ; une voix inventée `qwen3tts-1.7b-voicedesign` ;
#@markdown une voix prédéfinie `qwen3tts-1.7b-customvoice`. L'étape **Tâches** dit lesquels
#@markdown vos tâches demandent.
MODELES = 'qwen3tts-1.7b-base'  #@param {type:"string"}
#@markdown Qwen3-TTS est sous licence Apache-2.0 (page de chaque modèle sur Hugging Face).
#@markdown Cochez seulement après l'avoir lue : rien n'est téléchargé sans votre accord.
J_ACCEPTE_LES_LICENCES = False  #@param {type:"boolean"}
#@markdown `auto` : bfloat16 sur A100 et L4, float16 sur T4 — l'essai vérifie et se replie
#@markdown sur float32 si la prise n'est pas bonne.
PRECISION = 'auto'  #@param ["auto", "bfloat16", "float16", "float32"]
""", title='1. Paramètres'),
        code("""
#@title 2. Drive et GPU
from google.colab import drive
drive.mount('/content/drive')
import os
if not os.path.isfile(f'{PROJET}/personarp_colab.py'):
    raise SystemExit(f'Projet introuvable : {PROJET} — vérifiez le chemin dans les paramètres.')
!nvidia-smi --query-gpu=name,memory.total,compute_cap --format=csv
""", title='2. Drive et GPU'),
        code("""
#@title 3. Installer l'outil et son moteur de voix (à chaque session, 3 à 5 min)
""" + RUNNER + """ installer
""", title='3. Installer'),
        code("""
#@title 4. Modèles : téléchargés par l'outil, puis copiés sur Drive (la première fois seulement)
_modeles = ' '.join(f'--modele {nom.strip()}' for nom in MODELES.split(',') if nom.strip())
_licences = '--accepter-licences' if J_ACCEPTE_LES_LICENCES else ''
""" + RUNNER + """ modeles {_modeles} {_licences}
""", title='4. Modèles'),
        code("""
#@title 5. Essai : une réplique sur cette carte, et le choix de la précision
""" + RUNNER + """ essai --precision {PRECISION}
""", title='5. Essai'),
        code("""
#@title 6. Vérifier les tâches (rien n'est généré)
""" + RUNNER + """ taches
""", title='6. Tâches'),
        code("""
#@title 7. Lancer les tâches (interrompre la cellule arrête proprement ; relancer reprend)
""" + RUNNER + """ lancer
""", title='7. Lancer'),
        code("""
#@title 8. État
""" + RUNNER + """ etat
""", title='8. État'),
        markdown("""
### Bon à savoir

- **Reprendre** : si la session s'arrête, rouvrez le notebook, exécutez 1 à 3 puis 5 et 7 :
  les modèles sont déjà sur Drive, et chaque tâche reprend là où elle en était.
- **Refaire une tâche terminée** : retirez sa ligne de `resultats/_taches.json`.
- **Une seule tâche** : `lancer --tache nom-du-dossier`.
- Les voix inventées et prédéfinies demandent leurs propres poids : ajoutez-les à `MODELES`.
"""),
    ]
    return {'cells': cells, 'metadata': {
        'accelerator': 'GPU', 'colab': {'provenance': [], 'gpuType': 'T4'},
        'kernelspec': {'display_name': 'Python 3', 'name': 'python3'},
        'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 0}


def _ignore(directory, names):
    return [name for name in names if name in EXCLUDED or name.endswith('.pyc')]


def build(target=DEFAULT_TARGET):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    tool = target / 'outil'
    if tool.exists():
        shutil.rmtree(tool)
    shutil.copytree(APP, tool / 'app', ignore=_ignore)
    # No wheel: CyToolsCore is public, and the runner installs the commit requirements.txt pins.
    sdk = next(line for line in (APP / 'requirements.txt').read_text(encoding='utf-8').splitlines()
               if line.startswith('cytools-core'))

    shutil.copy2(APP / 'colab' / 'personarp_colab.py', target / 'personarp_colab.py')
    shutil.copy2(APP / 'colab' / 'LISEZ-MOI.md', target / 'LISEZ-MOI.md')
    shutil.copy2(ROOT / 'LICENSE', target / 'LICENSE')
    (target / 'PersonaRP_Colab.ipynb').write_text(
        json.dumps(notebook(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    for folder in ('modeles', 'resultats', 'taches'):
        (target / folder).mkdir(exist_ok=True)
    example = target / 'taches' / 'exemple-valdrenn'
    if not example.exists():
        (example / 'personnages').mkdir(parents=True)
        (example / 'liste.csv').write_text(EXAMPLE_LIST, encoding='utf-8')
        (example / 'tache.json').write_text(json.dumps(EXAMPLE_SETTINGS, ensure_ascii=False,
                                                       indent=2) + '\n', encoding='utf-8')
        shutil.copy2(APP / 'examples' / '01-valdrenn.zip', example / 'personnages' / 'valdrenn.zip')

    manifest = json.loads((APP / 'CyTool.json').read_text(encoding='utf-8'))
    files = sorted(path for path in tool.rglob('*') if path.is_file())
    (tool / 'VERSION.json').write_text(json.dumps({
        'tool': manifest['id'], 'version': manifest.get('version', ''),
        'built': time.strftime('%Y-%m-%dT%H:%M:%S'), 'files': len(files),
        'bytes': sum(path.stat().st_size for path in files),
        'sdk': sdk,
        'models': 'none — downloaded on Colab by the Tool'}, indent=2) + '\n', encoding='utf-8')
    weights = [path for path in target.rglob('*')
               if path.suffix.lower() in ('.safetensors', '.bin', '.pt', '.pth', '.gguf', '.onnx')
               and not path.is_relative_to(target / 'modeles')]
    if weights:
        raise SystemExit('A model file found its way into the project: %s' % weights[0])
    return target


def main():
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET)
    total = sum(path.stat().st_size for path in target.rglob('*') if path.is_file()
                and not path.is_relative_to(target / 'modeles')
                and not path.is_relative_to(target / 'resultats'))
    print('Colab project: %s (%.1f MB, no model)' % (target, total / 1e6))


if __name__ == '__main__':
    main()
