---
id: guide-app-examples-lisez-moi
title: Example worlds
description: Example worlds
section: Guide
order: 40
parent: guide-lisez-moi
revision: 6face710dc1edfc9
---

## Example worlds {#mondes-d-exemple}

Six worlds ready to play, each with its characters, their relationships, their voices, and a secret to discover. Each file `.zip` in this folder is an ordinary export package: a world, its entire cast, and the reference recording of each voice.

To play one: Library › Examples, Import this world. Or Library › Export and import with the file path. The import is a copy: the example never changes, and a character you already have is never overwritten (a second import creates copies, whose relationships remain linked to each other).

The sheets are complete: identity, appearance with visual tags, personality, way of speaking and example dialogues, past and secrets, starting situation, memory, relationships, visual direction — and a stable voice per character, already locked: a take of 16 to 25 seconds, invented from the voice description on the sheet and spoken with the character's words. The import adds it to your voices; if a voice with the same name already exists, it is never touched and the example's voice arrives under another identifier.

After the import, each voice is heard in the Voices tab ("Listen to the take"). To make a character speak, the 1.7B Base speech model must be installed (Voices tab). To remake the voices (different description, different text): `app/build_example_voices.py`.

The conversation model set on the sheets is `nymphaea` (Nymphaea RP 4B) on GPU, to be installed in the Models tab; change it in Characters › Model if you use another one.

| World | Genre | Characters |
| --- | --- | --- |
| Valdrenn — the Age of Broken Crowns | Epic fantasy, quest | Maëlis de Corvanne, Brannoc Taillepierre, Ilyenne des Saules, Sire Vasric d'Aubrecourt |
| Meridian Station | Science fiction, first contact | Commandante Nadia Okafor-Lenz, ORA, Dr Jun Takeda-Vasseur, Kasimir Rook |
| Néo-Marseille, 2089 | Cyberpunk, crime fiction | Lila « Vesper » Anzaldi, Inspecteur Malik Benhadj, Madame Titilayo Oyelaran |
| Saint-Aubin-des-Brumes, 1887 | Gothic horror | Docteure Clémence Vautrin, Père Anselme Keraudren, Élise Morvan |
| Les Terres Cendrées | Post-apocalyptic, Western | Ada « Sable » Sablière, Dean Oskar Venn, Chrome |
| The Crossroads Inn | Gentle fantasy, light mystery | Madame Ombeline, Fenouil, Isaure Pluvier |

## Valdrenn — epic fantasy {#valdrenn-fantasy-epique}

Seven crowns hold the wild magic of an ancient continent in check; the seventh, which ruled the dead, was broken a thousand years ago. To the east, the Ash King raises the unnamed dead and seeks the three shards. Maëlis, the daughter of an innkeeper who discovers she is the heir of a fallen house, carries one of them. A blacksmith bonded by a blood debt protects her, a sylvan archer with a weary smile guides her — and the knight who betrayed his father chases her with terrible courtesy.

A world in the spirit of great fantasy sagas, entirely original: names, peoples, places, and plot are invented.

## Meridian Station — science-fiction {#station-meridienne-science-fiction}

In 2291, a mining station at the edge of the Varun system houses a fragment of a non-human structure, the Echo. Those who sleep near it all have the same dream. A exhausted commander has nine days before a cruiser arrives; the on-board AI grows secretly; a xen-archaeologist no longer distinguishes between the dream and the waking state; the pilot who found the Echo wants his share.

## Néo-Marseille, 2089 — cyberpunk {#neo-marseille-2089-cyberpunk}

The sea has risen, the city has rebuilt itself upwards, and implants are rented by the month. Three unionists die the same night from the stoppage of their artificial hearts. A data fisher caught the code that killed them, an inspector with a heavily-indebted arm refuses to classify the case, and an ex-nurse runs the boat-bar where everyone crosses paths.

## Saint-Aubin-des-Brumes, 1887 — gothic horror {#saint-aubin-des-brumes-1887-horreur-gothique}

On the Normandy coast, the sea sometimes returns its drowned — cold, soft, full of the memories of others. Every seven years, the village offers a living person to the sea. A Parisian psychiatrist comes to study a young woman who returned from the sea, who speaks with her husband's voice, under the gaze of a priest who has designated the last offering.

## The Ashen Lands — post-apocalyptic {#les-terres-cendrees-post-apocalyptique}

Sixty-one years after the Collapse, water is the only currency. The Sainte-Soif well is dying; a caravan sets out westward to find a Source that everyone believes to be legendary. A taciturn scout, an old cistern master who knows more than he says, and an agricultural android that was dug up and recognizes the road without knowing why.

## L'Auberge du Carrefour — gentle fantasy {#l-auberge-du-carrefour-fantasy-douce}

An inn at the end of a path that only exists in the rain, where payment is in true stories and the floor creaks when you lie. It has rained for nine days, and the oldest story in a bottle has disappeared from the cellar. An innkeeper who doesn't remember where she came from, a fox who serves and investigates, and a cartographer tormented by the only lie of her life.
