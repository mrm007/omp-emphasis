# Context

omp Emphasis changes how an assistant reply is drawn in omp's terminal. It never changes what is stored, copied or exported. It is a port of pi-emphasis; only the border below and the pill tint differ from it.

## Glossary

- **Pill**: `[[Word]]` in a reply, drawn as a rounded chip. Its color and icon come from its word.
- **Word**: the known term a pill starts with, such as Done or Needs you. Matching ignores case and extra spaces.
- **Detail**: text after the word inside the same pill, such as the "12/12" in "Passed 12/12".
- **Tone**: the color group a word belongs to: error, warning, success, danger, mode, owner, or neutral for any unknown word.
- **Synonym**: a word that is displayed as another word, so one state always reads the same (Completed is shown as Done).
- **Label**: a `##` heading, or bold text that opens a line or list item. A known label takes an icon.
- **Lead-in**: a bold word ending in a colon that introduces the action a pill calls for, such as "Check:".
- **Reply guidance**: the rules added to the end of the system prompt as a `<reply_style>` block, in the terminal interface only.
- **Palette**: the colors taken from the current omp theme. It is rebuilt when the theme changes.
- **Tint**: a tone's pill color, made by moving the theme's tool panel color a quarter of the way toward the tone's own color. omp themes have no warning panel and often leave the success and error panels untinted.

## Rules and where each lives

All rules live in `index.ts` and are tested in `test/emphasis.test.ts` without omp running.

- Which tone a word has, and which words agents are told to write: `VOCABULARY` (`core` is taught, `also` is only accepted), read by `toneOf`.
- Which icon a pill word has: `PILL_ICONS`.
- Which words are synonyms: `SYNONYMS`.
- Which labels take an icon: `LABEL_ICONS`, applied by `withLabelIcon`.
- Which lead-in words take an icon after a pill: `ACTION_ICONS`.
- What the agent is told: `replyGuidance`, whose word lists are read from the tables above.
- How a pill label splits into icon, word and detail: `splitLabel`.
- What is left untouched (fenced code, inline code, escaped markers): `decorate` and `decorateLine`.

## Border

omp calls the extension's assistant text renderer with each text block of an assistant reply; the renderer returns that Markdown with terminal color codes added, using the theme captured at session start. While Tern's native view is drawing (`isNativeRendering()` from `@oh-my-pi/pi-tui/native/state`), Tern renders the Markdown itself and would show color codes as text, so the renderer adds labels and icons, turns tree rows into nested list items, and writes each pill as a link to `#omp-pill-<tone>` when Tern has this repository's plugin (`tern/`), else as a code span. The plugin is a global Tern sheet, `tern/pills.css`, that draws those links as pills; it is the only part of omp Emphasis that runs in Tern. omp runs these renderers only while the `extensionRenderers.assistantText` setting is on. Before each prompt in the terminal interface, the extension appends the reply guidance to the system prompt blocks omp passes to `before_agent_start`. Nothing else crosses.
