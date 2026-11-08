# Visual assembly hard gate

An approved A-roll image approves the artwork only, never a different presentation shell. Every ordinary A-roll composition must contain `data-aroll-paper`, `data-aroll-stage`, and `data-aroll-artwork`, with outer `#f8f7f6`, inner `#fdfaf4`, and locked 72/72/70/820 geometry. Never stretch the approved image over the 1920×1080 root or replace the shell with a dark full-screen background.

Opening title and opening transition must point to the exact fixed files under `assets/arroll/fixed/`; a custom imitation fails. Chapter/subchapter fixed roles follow [fixed-aroll-system.md](fixed-aroll-system.md).

A registered B-roll instance records `templateSourcePath` and `templateSourceHash` and preserves the source template's HTML structure. Content text, composition ID, duration, and narration timing may change; tag/class/data-role structure may not. One generic panel reused under different template IDs fails.

Scripts may record deterministic checks and provenance, but must not invent `humanChecks`, approval records, or claim a user reviewed output. Explicit human approval can only be recorded after the user actually approves the presented review artifact.

`validate_preview_ready.py` runs `validate_visual_assembly.py` and rejects missing or stale `visualAssembly` evidence. Do not create, serve, or request approval for a preview that fails this gate.
