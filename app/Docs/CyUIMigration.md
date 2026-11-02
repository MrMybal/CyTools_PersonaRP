# Modular CyUI integration

The standalone application uses [CyUI](https://github.com/MrMybal/CyUI) 1.2.0,
pinned to [`ff023e6`](https://github.com/MrMybal/CyUI/tree/ff023e646c6a3038b3dfbfd53f6d2b4a2f5955e3).

## Selected modules and replacements

Core; DocumentViews (documents); Code; Images; Canvas; Diagnostics.

- Free discussions use the common cached Markdown transcript with one state per thread. Closing a thread prunes its presentation cache.
- The large picture viewer uses Images and its pointer navigation; decoding/texture ownership remains with the host.
- Structured logs use Diagnostics, with a character-selectable text tab.
- Core replaces the previous local monolith; no model/provider logic moves into the UI library.

## Reproducible source and delivery

`app/cyui-source.json` records every selected upstream file and its SHA-256.
`app/cyui.py` and `app/cyui_modules/*.py` are unchanged official sources, normalized
to LF. Do not edit them: host adapters live outside the library. Refresh only from
the exact pinned checkout:

```sh
python app/scripts/sync_cyui.py /path/to/CyUI
```

The sources are included with the application using its existing source-vendoring
mechanism. Neither a developer checkout elsewhere on disk nor an editable pip
installation is needed. There is one imgui-bundle renderer, at the version pinned
in `app/requirements.txt`; no C++ umbrella, CMake demo/gallery, CEF, extra model,
AI engine, NumPy installation or browser dependency is introduced by this migration.
Existing application/DSP/rendering dependencies are kept where required.

Keep `LICENCES/CyUI-MIT.txt` with the product. The application's own license does
not change. The Options licenses list identifies the upstream revision and source.

## Host responsibilities and retained adaptations

Character/world schemas, scene directives, voice annotations, streaming jobs, attachments, galleries and persistence remain host-owned. The roleplay scene retains its specialized editable directives, speech actions and media controls. DocumentViews is a documented Markdown subset, not a browser/Discord implementation. HTTP(S) links returned by it are handled by the host. No Web/CEF engine or unused Inspector is shipped.

SDK operations, permissions, exclusive groups, temporary AI task files, model
installation, licenses/acceptance, generation recipes and Undo remain host-owned.
No CyToolsCore runtime or AI library is copied into CyUI. English remains the
default and French the persistent selectable second language.

## Verification

305 existing tests passed, one skipped; four new integration tests passed. Native Scene, Assistant, Assistant-Proposal, log and options views passed.

Run the adapter tests from `app/` with the private Python:

```sh
python -m unittest discover -s tests -p test_modular_ui.py -v
```

They verify pinned-source integrity, bounded log refresh/redaction and native ImGui
frames across five themes, both densities, EN/FR and scale 1.0/1.5/2.0, plus the
application-specific data/edit routing. This simulated DPI check is not a physical
multi-monitor test. Windows native views are tested locally. Linux/macOS remain
unverified by this migration; the source integration stays platform-independent.

Windows packages include the migrated sources and their license notices.

Final local results: 305 existing pytest tests passed and 1 skipped, plus 4 new adapter tests passed. Native checks passed for five EN views and nine FR view/subview combinations. A separate native fixture rendered the new picture surface and a Markdown conversation with bold, code and a table; capture: data/reports/cyui-native-picture-markdown.png.


CyUI license: [https://github.com/MrMybal/CyUI/blob/main/LICENSE](https://github.com/MrMybal/CyUI/blob/main/LICENSE). The complete MIT text ships with the application, including when the upstream repository is private.
