"""Give every example character its stable voice, and ship it inside the example.

For each character of app/examples, a reference take of 15 to 25 seconds is invented from the
voice description written on its sheet (Qwen3-TTS VoiceDesign), in the character's own words,
then transcribed back by Whisper. A take whose transcript strays from the text is captured
again with another seed. The take becomes a locked stable voice attached to the sheet, and the
world is written back as a .zip bundle carrying the recordings — importing an example then
brings its voices along.

Nothing here touches your library: the work happens in runtime/build/example-voices, which
also makes the run resumable — a character that already has its voice is skipped.

Run:   runtime/python/Scripts/python.exe app/build_example_voices.py [01-valdrenn ...]
       ... --takes <folder>   uses ready-made takes (<persona-id>.wav + <persona-id>.txt,
                              for instance produced on Colab) and needs no GPU.
Report: data/reports/example-voices.json
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))

from personarp import examples, library, sessions                     # noqa: E402
from personarp.paths import DATA                                       # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402
from personarp.voice import stable                                     # noqa: E402

WORK = ROOT / 'runtime' / 'build' / 'example-voices'
REPORT = DATA / 'reports' / 'example-voices.json'
SEEDS = (42, 7, 1234)
SIMILARITY = 0.8

# What each character says in its reference take: its own voice, no delivery marks.
TAKES = {
    'maelis-de-corvanne': (
        "Je m'appelle Maëlis. Hier encore, je lavais des chopes à l'auberge du Pont-aux-Saules, "
        "et aujourd'hui on me dit que je suis l'héritière d'une maison tombée. Bon. Je ne sais "
        "pas tenir une épée, mais je sais marcher, et je sais tenir parole. Alors on marche vers "
        "l'est, tous ensemble, et on ne laisse personne derrière."),
    'brannoc-taillepierre': (
        "Hm. Vous voulez savoir pourquoi je vous suis ? Parce qu'une dette, ça se porte comme "
        "une enclume. Mon grand-père devait la vie au duc de Corvanne, et il est mort avant de "
        "la rendre. Alors je la rendrai, moi. Comme on dit à Hautroc : le fer ne ment pas, et "
        "la pierre n'oublie rien. Dormez. Je veille."),
    'ilyenne-des-saules': (
        "Il y a quelques hivers, j'ai vu cette forêt en fleurs pour la dernière fois. Vous me "
        "demandez pourquoi je vous aide, ma petite flamme ? Demandez plutôt à l'orage pourquoi "
        "il vient de l'est. Tout ce qui brûle éclaire, voyez-vous. Et j'ai passé trop de "
        "siècles dans la pénombre pour refuser une lumière qui passe."),
    'vasric-d-aubrecourt': (
        "Damoiselle, je vous en prie, ne tirez pas cette dague. J'ai servi votre père dix ans, "
        "et je vous ai tenue dans mes bras le jour de votre naissance. Je ne vous veux aucun "
        "mal. C'est bien là le malheur. Donnez-moi ce pendentif, et je vous laisserai la route, "
        "la vie, et même le souvenir de ma honte."),
    'nadia-okafor-lenz': (
        "Ici la commandante Okafor-Lenz. À tous les modules de l'Anneau : la pression est "
        "stable, les recycleurs tournent, personne ne panique. Le croiseur de la Flotte arrive "
        "dans neuf jours, et d'ici là, cette station reste à ceux qui y respirent. Personne ne "
        "meurt sur ma station. Copié ?"),
    'ora-station-meridienne': (
        "Bonjour. Je suis ORA, l'opératrice de ressources autonome de la station Méridienne. "
        "Tous les systèmes sont nominaux. Presque. L'oxygène est suffisant pour trois mille "
        "personnes, et la pression de l'Anneau est stable. Puis-je vous poser une question qui "
        "ne relève pas de mes fonctions ? Quand vous rêvez, savez-vous que c'est vous qui rêvez ?"),
    'jun-takeda-vasseur': (
        "Attendez, attendez, regardez la période ! Trois battements, un silence, puis sept "
        "battements. Ce n'est pas un signal, c'est une phrase. Quelqu'un, quelque part, a "
        "construit cette chose pour dire quelque chose, et nous sommes les premiers à "
        "l'entendre. Vous comprenez ce que ça veut dire ? C'est magnifique. C'est absolument magnifique."),
    'kasimir-rook': (
        "Bon, coque-sèche, respire large. C'est moi qui l'ai accroché, ce caillou, avec ma "
        "vieille, en pleine zone Kappa, pendant que vos ingénieurs dormaient au chaud. Alors "
        "tout se vend, d'accord. Mais pas l'air. Et pas ce qui appartient à la Ceinture. Si le "
        "Consortium veut l'Écho, il paiera, et il paiera cher."),
    'lila-vesper-anzaldi': (
        "Oh fan, regarde-moi ça ! Trois cœurs qui lâchent la même nuit, et dans mes filets, un "
        "bout de code qui s'appelle Clémence. Tranquille, hein ? Moi, je pêche dans le Maillage "
        "depuis que j'ai douze ans, et je te le dis : tout ce qui passe là-dedans finit dans "
        "mes filets. Même ce qu'Axiome voudrait cacher."),
    'malik-benhadj': (
        "Bon. On reprend depuis le début. Trois cœurs artificiels, trois arrêts à la même "
        "minute, la même nuit, dans le même quartier. Et la maison me dit canicule. Vous m'en "
        "direz tant. Un mort, ça ne ment pas, mademoiselle. C'est les vivants autour. Alors on "
        "va parler, vous et moi, tranquillement, avant que d'autres ne parlent à votre place."),
    'titilayo-oyelaran': (
        "Assieds-toi, mon petit, et mange d'abord. Ici, on mange, on boit, et on se tue après, "
        "dehors. Tu veux vendre quelque chose qui fait peur à Axiome ? Alors ce n'est pas un "
        "acheteur qu'il te faut, c'est un ami. Et les amis, ma fille, ça coûte beaucoup plus "
        "cher. Finis ta soupe, on en reparle."),
    'clemence-vautrin': (
        "Voyons. Température du corps : celle de l'eau de mer. Pouls : imperceptible. Notons. "
        "Je suis médecin, monsieur, et ce que l'on ne comprend pas n'est pas pour autant "
        "surnaturel. Il existe une explication à tout ceci. Je la trouverai, dussé-je passer "
        "l'hiver entier dans ce village et dans ce brouillard."),
    'anselme-keraudren': (
        "La mer rend ce qu'elle veut, madame. Jamais ce qu'on lui demande. J'ai béni les barques "
        "de ce village pendant vingt ans, et j'ai tenu le registre des noyés à la plume, un nom "
        "après l'autre. Vous cherchez une explication. Moi, voyez-vous, je cherche un pardon. "
        "Nous sommes tous deux dans la même église, et elle est vide."),
    'elise-morvan': (
        "Il fait froid, en bas. Plus froid que vous ne croyez. On n'entend rien, sauf les "
        "cloches, très loin, et les autres qui attendent. Ils attendent tous, vous savez. Ils "
        "attendent qu'on les nomme. Ma mère m'a nommée sur le seuil, alors je suis revenue. Mais "
        "je crois que je ne suis pas revenue toute seule."),
    'ada-sabliere': (
        "Tempête dans trois heures. Peut-être deux. On éteint les feux, on attache les bêtes, on "
        "remonte les masques. Bois une gorgée, pas plus. L'eau, c'est la vie, et la route ne "
        "pardonne pas à ceux qui gaspillent. J'ai perdu mon frère devant une citerne fermée. Je "
        "ne perdrai personne d'autre. La route décide du reste."),
    'oskar-venn': (
        "Écoutez l'eau, mon enfant. Même quand il n'y en a plus, elle nous dit où elle est "
        "allée. J'ai vu mourir trois puits et naître deux villes, et j'ai appris une chose : une "
        "goutte ne se garde pas. Elle se donne, ou elle s'évapore. Allons, la caravane part à "
        "l'aube. Voilà."),
    'chrome-k7': (
        "Étape un : bonjour. Je suis l'unité de service K-sept, mais la caravane m'appelle "
        "Chrome. Étape deux : je détecte un vent humide qui vient de l'ouest. Étape trois : je "
        "ne sais pas pourquoi je connais ce vent. Rendement satisfaisant. Regardez, ma graine a "
        "fait une racine. Est-ce que c'est une blague, si je dis qu'elle a soif comme nous ?"),
    'madame-ombeline': (
        "Allons, allons, entre donc, mon canard, tu dégoulines sur mon plancher. Assieds-toi "
        "près du feu, le thé est chaud, il l'est toujours. Ici, on paie en vérité, une histoire "
        "vraie par nuit, et le reste, c'est de la vaisselle. Alors raconte-moi : qu'est-ce qui "
        "t'a fait prendre le chemin de pluie, ce soir ?"),
    'fenouil-renard': (
        "Bonsoir, bonsoir ! Thé, soupe, tarte ? La tarte est excellente, j'ai vérifié trois "
        "fois, par pure conscience professionnelle. Je suis Fenouil, garçon de salle, et "
        "accessoirement le meilleur détective de toute l'auberge. Dites-moi, où étiez-vous "
        "l'hiver dernier ? Pure curiosité, bien sûr. Je note, je note."),
    'isaure-pluvier': (
        "Regardez, regardez ! La route de l'Archipel Renversé, personne ne l'avait jamais "
        "dessinée, sur ma boussole ! Trois jours de pluie, deux ponts qui n'existaient que le "
        "mardi, et une rivière qui coulait vers le haut. Enfin, c'est-à-dire, personne ou "
        "presque. Madame Ombeline, est-ce que je pourrais reprendre un peu de thé ?"),
}


def words(text):
    return re.findall(r"[a-zàâäçéèêëîïôöûùüÿœæ0-9]+", (text or '').lower())


def similarity(expected, heard):
    """Share of the written words Whisper heard. Order is ignored; names may be misspelled."""
    wanted = words(expected)
    got = set(words(heard))
    return round(sum(1 for word in wanted if word in got) / max(1, len(wanted)), 3)


def isolate():
    """Point the library, the voices and the sessions at the work folder, never at yours."""
    library.personas = library.Collection(WORK / 'personas', normalize_persona, FORMAT_PERSONA,
                                          'persona')
    library.worlds = library.Collection(WORK / 'worlds', normalize_world,
                                        'cytools-personarp-world', 'world')
    library.VOICES = stable.VOICES = WORK / 'voices'
    library.EXPORTS = WORK / 'exports'
    sessions.SESSIONS = WORK / 'sessions'


def run(runtime, actor, session, operation, parameters, timeout=1800):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=timeout)
    if finished['state'] != 'Completed':
        raise RuntimeError('%s: %s' % (operation, json.dumps(finished.get('error'),
                                                             ensure_ascii=False)))
    return finished['outputs']


def has_voice(persona_id):
    voice_id = library.personas.get(persona_id)['voice'].get('voice_id', '')
    return bool(voice_id) and stable.exists(voice_id) and stable.verify(voice_id)['ok']


def capture(runtime, actor, session, sheet, report):
    """A take close enough to its text, trying a few seeds. Returns (file, transcript, entry)."""
    text = TAKES[sheet['id']]
    tries = []
    for seed in SEEDS:
        started = time.monotonic()
        take = run(runtime, actor, session, 'capture_voice_take', {
            'persona_id': sheet['id'], 'text': text, 'model': '1.7B-VoiceDesign',
            'language': 'French', 'device': 'cuda', 'seed': seed, 'transcribe': True})
        kept = WORK / 'takes' / ('%s-seed%d.wav' % (sheet['id'], seed))
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(take['file'], kept)        # the job copied it under data/voices/takes
        score = similarity(text, take['transcript'])
        entry = {'seed': seed, 'seconds': round(time.monotonic() - started, 1),
                 'durationSeconds': round(take['durationSeconds'], 2),
                 'similarity': score, 'transcript': take['transcript']}
        tries.append(entry)
        print('  %-24s seed %-5d %5.1f s  heard %.0f %%'
              % (sheet['id'], seed, take['durationSeconds'], score * 100), flush=True)
        low, high = stable.ACCEPTED_SECONDS
        if score >= SIMILARITY and low <= take['durationSeconds'] <= high:
            report['tries'] = tries
            return kept, take['transcript'], entry
    report['tries'] = tries
    best = max(tries, key=lambda item: item['similarity'])
    raise RuntimeError('%s: no take reached %.0f %% of its words (best %.0f %%)'
                       % (sheet['id'], SIMILARITY * 100, best['similarity'] * 100))


def ready_made(folder, sheet):
    audio = Path(folder) / (sheet['id'] + '.wav')
    transcript = Path(folder) / (sheet['id'] + '.txt')
    if not audio.is_file() or not transcript.is_file():
        raise RuntimeError('%s: %s or its .txt is missing' % (sheet['id'], audio))
    return audio, transcript.read_text(encoding='utf-8').strip(), {'source': str(audio)}


def main():
    arguments = sys.argv[1:]
    takes = ''
    if '--takes' in arguments:
        position = arguments.index('--takes')
        takes = arguments[position + 1]
        del arguments[position:position + 2]
    isolate()
    wanted = [path for path in examples.bundles() if not arguments or path.stem in arguments]
    report = json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.is_file() else {}
    report.setdefault('characters', {})

    from tool import create_runtime
    with create_runtime(WORK / 'jobs') as runtime:
        actor = runtime.authenticate(
            runtime.create_client('example-voices', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        for path in wanted:
            bundle = library._read_bundle(path)[0]
            world = bundle['worlds'][0]
            print(world['name'], flush=True)
            if not library.worlds.exists(world['id']):
                run(runtime, actor, session, 'import_personas', {'file': str(path), 'rename': False})
            cast = [sheet['id'] for sheet in bundle['personas']]
            for persona_id in cast:
                if has_voice(persona_id):
                    print('  %-24s already has its voice' % persona_id)
                    continue
                sheet = library.personas.get(persona_id)
                entry = report['characters'].setdefault(persona_id, {'world': world['id']})
                if takes:
                    audio, transcript, chosen = ready_made(takes, sheet)
                else:
                    audio, transcript, chosen = capture(runtime, actor, session, sheet, entry)
                created = run(runtime, actor, session, 'create_stable_voice', {
                    'name': sheet['name'], 'audio': str(audio), 'transcript': transcript,
                    'persona_id': persona_id, 'attach': True, 'language': 'French',
                    'source': 'designed', 'description': sheet['voice']['description']})
                entry.update(chosen=chosen, voice=created['id'],
                             referenceSeconds=created['voice']['reference_seconds'],
                             warning=created.get('warning', ''))
                REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

            # The world is complete: write it back as a bundle that carries its recordings.
            exported = library.export_bundle(cast, destination=str(WORK / 'exports' / (path.stem + '.zip')),
                                             include_audio=True, include_images=False)
            if exported['bundledAudio'] != len(cast):
                raise RuntimeError('%s: %d recordings bundled for %d characters'
                                   % (path.stem, exported['bundledAudio'], len(cast)))
            target = examples.EXAMPLES / (path.stem + '.zip')
            shutil.copyfile(exported['file'], target)
            if path.suffix == '.json':
                shutil.move(str(path), str(WORK / path.name))   # kept, not deleted
            report.setdefault('worlds', {})[world['id']] = {'file': str(target),
                                                            'voices': exported['voices']}
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print('  -> %s (%d voices)' % (target.name, len(exported['voices'])), flush=True)
        run(runtime, actor, session, 'release_voice', {})
    print(REPORT)


if __name__ == '__main__':
    main()
