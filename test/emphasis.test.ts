import { describe, expect, test } from "bun:test";
import { CONTEXT_WORDS, VOCABULARY, chipColors, createPalette, decorate, replyGuidance, toneOf, type ThemeLike } from "../index.ts";

// A theme whose colors are readable tags, so tests can assert on what was colored.
const theme = {
	fg: (color: string, text: string) => `<${color}>${text}</>`,
	getFgAnsi: (color: string) => `\x1b[38;fg-${color}m`,
	getBgAnsi: (color: string) => `\x1b[48;bg-${color}m`,
} as unknown as ThemeLike;
const palette = createPalette(theme);
const plain = (text: string) => decorate(text, palette).replace(/\x1b\[[0-9;a-zA-Z-]*m/g, "").replace(/[\ue0b4\ue0b6]/g, "|").replace(/\u00a0/g, " ");

describe("pill tone", () => {
	test.each([
		["Failed", "error"], ["Blocked", "error"], ["Needs you", "warning"], ["Decision", "warning"],
		["Done", "success"], ["Observed", "success"], ["Costs money", "danger"], ["Irreversible", "danger"],
		["Implement", "mode"], ["Shared", "owner"], ["Inferred", "neutral"], ["Anything else", "neutral"],
	])("%s is %s", (word, tone) => expect(toneOf(word)).toBe(tone as never));

	test("case and spacing do not matter", () => expect(toneOf("  needs   YOU ")).toBe("warning"));
	test("a known word may carry detail", () => {
		expect(toneOf("Passed 12/12")).toBe("success");
		expect(toneOf("Failed: 3 tests")).toBe("error");
	});
	test("a longer word that starts like a known one is not that word", () => expect(toneOf("Donezo")).toBe("neutral"));
});

describe("pills", () => {
	test("a known word gets its icon", () => expect(plain("[[Done]]")).toBe("|\uf00c Done|"));
	test("an unknown word has no icon", () => expect(plain("[[Anything else]]")).toBe("|Anything else|"));
	test("synonyms display as one word and keep their detail", () => {
		expect(plain("[[Completed]]")).toBe("|\uf00c Done|");
		expect(plain("[[Fail: 3 tests]]")).toBe("|\uf00d Failed: 3 tests|");
	});
	test("a label's own glyph wins over the table's", () => expect(plain("[[\uf0e7 Done]]")).toBe("|\uf0e7 Done|"));
	test("labels over 32 characters are left alone", () => {
		const long = `[[${"x".repeat(33)}]]`;
		expect(plain(long)).toBe(long);
	});
});

describe("labels", () => {
	test("a heading takes an icon from its word", () => expect(plain("## Finding")).toBe("## \uf002 Finding"));
	test("an unknown heading is untouched", () => expect(plain("## What happened")).toBe("## What happened"));
	test("a leading bold label takes an icon, after list markers and tree connectors", () => {
		expect(plain("**Cause:** x")).toBe("**<mdLink>\uf0e7 Cause:</>** x");
		expect(plain("- **Fix:** x")).toBe("- **<mdLink>\uf0ad Fix:</>** x");
		expect(plain("  ├── **Risk:** x")).toBe("  <dim>├──</> **<mdLink>\uf071 Risk:</>** x");
	});
	test("bold later in a line gets color but no icon", () => expect(plain("see **Cause** here")).toBe("see **<mdLink>Cause</>** here"));
});

describe("action lead-ins", () => {
	test("take an icon anywhere in a line when they end in a colon", () => {
		expect(plain("[[Unverified]] red pills. **Check:** run it")).toBe("|\uf128 Unverified| red pills. **<mdLink>\uf046 Check:</>** run it");
		expect(plain("- **Unblock:** access")).toBe("- **<mdLink>\uf09c Unblock:</>** access");
	});
	test("get exactly one icon at the start of a line", () => expect(plain("**Next:** go")).toBe("**<mdLink>\uf061 Next:</>** go"));
	test("without a colon they are ordinary bold", () => expect(plain("please **do** it and **run** that")).toBe("please **<mdLink>do</>** it and **<mdLink>run</>** that"));
});

describe("what is left alone", () => {
	test("fenced code", () => {
		const block = "```\n**Cause:** → [[Done]]\n```";
		expect(plain(block)).toBe(block);
	});
	test("inline code", () => expect(plain("`[[Done]] → **x**`")).toBe("`[[Done]] → **x**`"));
	test("escaped asterisks", () => expect(plain("\\*\\*not bold\\*\\*")).toBe("\\*\\*not bold\\*\\*"));
});

test("arrows, checks and crosses take their colors", () => {
	expect(plain("a → b ✓ c ✗")).toBe("a <accent>→</> b <success>✓</> c <error>✗</>");
});

test("icons can be turned off", () => {
	process.env.PI_EMPHASIS_PILL_ICONS = "0";
	try {
		expect(plain("[[Done]]")).toBe("|Done|");
		expect(plain("## Finding")).toBe("## Finding");
	} finally {
		delete process.env.PI_EMPHASIS_PILL_ICONS;
	}
});

// A 24-bit theme: a dark panel, an orange warning, and black for every other color.
const truecolor = {
	fg: (_color: string, text: string) => text,
	getFgAnsi: (color: string) => (color === "warning" ? "\x1b[38;2;255;179;71m" : "\x1b[38;2;0;0;0m"),
	getBgAnsi: () => "\x1b[48;2;15;18;22m",
} as unknown as ThemeLike;

test("tone pills tint the tool panel with the tone's color, or fall back to reverse video", () => {
	const warning = createPalette(truecolor).pills!.warning;
	expect(warning.label).toBe("\x1b[48;2;75;58;34m\x1b[38;2;255;179;71m");
	expect(warning.cap).toBe("\x1b[38;2;75;58;34m");
	// The tag theme's colors are not 24-bit, so there is nothing to tint.
	expect(palette.pills!.warning).toEqual({ label: "\x1b[38;fg-warningm\x1b[7m", cap: "\x1b[38;fg-warningm" });
});

describe("native view, which draws the Markdown itself", () => {
	const native = (text: string) => decorate(text, { bold: (bold) => bold, native: true });
	test("pills become code spans and nothing is colored", () => {
		expect(native("**Result:** [[Completed]] build → [[Failed: 3 tests]] ✓")).toBe("**\uf11e Result:** `\uf00c Done` build → `\uf00d Failed: 3 tests` ✓");
		expect(native("**bold [[Needs you]] still bold**")).toBe("**bold `\uf007 Needs you` still bold**");
		expect(native("`[[Done]]` stays code")).toBe("`[[Done]]` stays code");
	});
	test("tree rows become nested list items, at any depth and under a list item", () => {
		expect(native("root\n├── **Fix:** api\n│   └── child\n└── [[Done]] worker")).toBe("root\n- **\uf0ad Fix:** api\n    - child\n- `\uf00c Done` worker");
		expect(native("- **Evidence:**\n  ├── one\n  └── two")).toBe("- **\uf06e Evidence:**\n  - one\n  - two");
		expect(native("```\n├── kept\n```")).toBe("```\n├── kept\n```");
	});
	test("with 24-bit theme colors, pills become math color boxes with the icon outside", () => {
		const math = (text: string) => decorate(text, { bold: (bold) => bold, native: true, chipColors: chipColors(truecolor) });
		expect(math("[[In progress 40%]] now")).toBe("\uf110 $\\colorbox{#4b3a22}{\\textcolor{#ffb347}{\\text{In progress 40\\%}}}$ now");
		expect(math("[[Costs money]]")).toBe("\uf155 $\\colorbox{#c0392b}{\\textcolor{#ffffff}{\\text{Costs money}}}$");
		// A backslash, caret or tilde has no simple escape, so that pill stays a code span.
		expect(math("[[a~b]]")).toBe("`a~b`");
		expect(chipColors(theme)).toBeUndefined();
	});
});

describe("reply guidance", () => {
	const text = replyGuidance();
	test("names every core word, and each one is colored as its tone", () => {
		for (const [tone, words] of Object.entries(VOCABULARY)) {
			for (const word of words.core) {
				expect(text).toContain(`[[${word}]]`);
				expect(toneOf(word)).toBe(tone as never);
			}
		}
		for (const word of CONTEXT_WORDS) expect(text).toContain(`[[${word}]]`);
	});
	test("every pill it mentions is a known word, so no example teaches an uncolored one", () => {
		const known = new Set([...Object.values(VOCABULARY).flatMap((w) => w.core), ...CONTEXT_WORDS, "Word"]);
		for (const [, label] of text.matchAll(/\[\[([^\]]+)\]\]/g)) expect([...known].some((k) => label === k || label.startsWith(`${k} `) || label.startsWith(`${k}:`))).toBe(true);
	});
	test("every lead-in it lists gets an icon", () => {
		for (const word of ["Check", "Do", "Next", "Unblock", "Left", "Run", "Guard", "Undo", "See"]) {
			expect(text).toContain(`**${word}:**`);
			expect(plain(`x **${word}:** y`)).not.toBe(`x **<mdLink>${word}:</>** y`);
		}
	});
	test("addresses any user", () => expect(text).not.toMatch(/\bJohn\b|~\/dev/));
});
