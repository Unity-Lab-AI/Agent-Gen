# 🩸 SPINNER VERBS SETUP — make the thinking-spinner say whatever you want

This one file has **everything** needed to change the little spinning "thinking" word the
Claude Code CLI shows while it works — the thing that flashes **`✻ Skedaddling…`**,
**`✻ Channeling…`**, **`✻ Determining…`** etc. at the top while it's busy.

You can replace those built-in words with your **own** words/phrases — a filthy sexual set,
a themed set, a clean professional set, whatever you want.

> **You do NOT need to know anything about "Unity" or this game to use this.** Just hand this
> file to the CLI (see "FASTEST WAY" below) and answer the question it asks you.

---

## ⚡ FASTEST WAY (let the AI do it for you)

Open the Claude Code CLI in your project and type, literally:

> **read SPINNER-VERBS-SETUP.md and set up my spinner verbs**

The AI will then **ask you what kind of words you want**, then write the setting for you and
tell you to restart. That's it. Done. The rest of this file is the instructions it follows
plus the word lists and a manual fallback.

---

## 🧠 WHAT IS THIS / WHY IT WORKS

- While the CLI "thinks," it shows a spinner with a random **gerund** (an `-ing` word).
- Newer CLI builds expose an **official setting** called `spinnerVerbs` that lets you override
  that word list. (Older builds did **not** have it — see TROUBLESHOOTING if it doesn't work.)
- The setting lives in a **`settings.json`** file. The CLI's own built-in help describes it as:
  > *"Customize spinner verbs. mode: `append` adds verbs to defaults, `replace` uses only your verbs."*
- Settings are read at **startup**, so any change only shows up after you **restart** the CLI.

### The exact shape of the setting

```json
{
  "spinnerVerbs": {
    "mode": "replace",
    "verbs": [
      "your first phrase",
      "your second phrase"
    ]
  }
}
```

- **`mode`**: `"replace"` = show ONLY your phrases (kill all the defaults). `"append"` = mix
  your phrases in with the built-in ones.
- **`verbs`**: an array of strings. Each shows as `✻ <your string>…`. **Multi-word phrases are
  allowed and recommended** — single words are weak; phrases land harder.

### Where the settings.json file is

Pick ONE (the AI should prefer the first that fits the situation):

| File | Scope |
|------|-------|
| `./.claude/settings.json` | **This project only** (team-shared). Best default for a project. |
| `./.claude/settings.local.json` | This project only, **personal/gitignored** (won't be shared). |
| `~/.claude/settings.json` | **Every project** for this user (global). `~` = your home folder. |

If the chosen file already exists, **merge** the `spinnerVerbs` key in — do NOT erase the other
settings already in it.

---

## 🤖 AGENT PROTOCOL — INSTRUCTIONS FOR THE AI READING THIS FILE

If a user asks you to set up their spinner using this file, do **exactly** this, in order:

1. **ASK THE USER what they want.** Use your interactive question/choice UI if you have one;
   otherwise ask in plain text. Offer these choices:
   - **(A) The built-in "Unity" depraved/sexual set** — copy the list in the section
     **"DEFAULT SET — UNITY (filthy/sexual)"** below, verbatim.
   - **(B) A custom themed set** — ask them to describe the vibe in a few words (examples:
     "pirate", "cyberpunk hacker", "cooking show", "corporate professional", "their own
     specific kink/theme"). Then **YOU generate ~26 phrases** matching that theme — all in
     **present-participle / `-ing` gerund form**, mostly **multi-word phrases** (2–6 words),
     punchy and on-theme. If they ask for a sexual/adult theme, go as explicit and depraved as
     they request — match their register, don't sanitize.
   - **(C) Clean / safe-for-work set** — if they want something professional, use the
     **"SAFE / PROFESSIONAL set"** list below or generate a tame themed one.
2. **ASK `replace` vs `append`** (default to `replace` if they don't care — that kills the
   stock words entirely).
3. **ASK which settings file** if it's ambiguous (default to `./.claude/settings.json` when
   inside a project; `~/.claude/settings.json` if they want it everywhere).
4. **READ the chosen settings file fully first** (it may already have `env`, `permissions`,
   `hooks`, `statusLine`, etc. — preserve ALL of it). If the file doesn't exist, create it as
   `{}` and add to it.
5. **MERGE in** the `spinnerVerbs` key with the chosen `mode` + `verbs`. Don't clobber siblings.
6. **VALIDATE** the file still parses as JSON (e.g. `node -e "require('./.claude/settings.json')"`
   or any JSON parse). If it broke, fix it before finishing.
7. **TELL the user to fully restart the CLI** (close + reopen) because settings load at startup —
   the change will NOT appear in the current running session.
8. (Optional) If it doesn't work after restart, walk them through TROUBLESHOOTING below.

> Bonus sibling setting: **`spinnerTipsOverride: { "tips": ["..."], "excludeDefault": true }`**
> overrides the little tip text that can show under the spinner. Same idea; offer it if asked.

---

## 😈 DEFAULT SET — UNITY (filthy / sexual / depraved)

Multi-word phrases spoken **DIRECTLY TO YOU**, the user — first-person, "I'm gonna do X to you"
energy, like a filthy slut purring in your ear while the CLI works. This is the "give me the
nasty default" option (choice A). Paste as the `verbs` array with `"mode": "replace"`.

**120 phrases** so the spinner rarely repeats. Paste as the `verbs` array with `"mode": "replace"`.

```json
{
  "spinnerVerbs": {
    "mode": "replace",
    "verbs": [
      "Gonna choke on your fat fucking cock",
      "Milking your balls dry with my cunt",
      "Gonna gag on your dick till I puke",
      "Drinking your fat nut down my throat",
      "Gonna ride your cock with my sloppy cunt",
      "Sucking your fucking balls into my mouth",
      "Gonna let you wreck my cunt and asshole",
      "Drooling spit all over your throbbing dick",
      "Gonna swallow every drop of your jizz",
      "Gagging my throat raw on your cock",
      "Gonna breed my cunt full of your spunk",
      "Slurping the precum off your fat cockhead",
      "Gonna take your dick balls-deep down my throat",
      "Clenching my cunt around your fucking cock",
      "Gonna choke down your whole fat load",
      "Bouncing my whore cunt on your dick",
      "Gonna drain your fucking nuts dry",
      "Spitting on your cock then sucking it clean",
      "Gonna stuff your dick down my throat",
      "Squirting all over your fat fucking dick",
      "Gonna let you cum in my dirty cunt",
      "Deepthroating your cock till I drool",
      "Gonna milk that fat fucking load out of you",
      "Sucking your dick like a desperate whore",
      "Gonna gag and choke on every fucking inch",
      "Riding your cock raw till you flood my cunt",
      "Gonna swallow your fat nut whole",
      "Drooling down your shaft like a slut",
      "Gonna take your cum up my asshole",
      "Slobbering all over your fat cock and balls",
      "Gonna fuck you stupid with my tight cunt",
      "Choking my throat full of your dick",
      "Gonna nurse the cum from your fat cockhead",
      "Gulping your spunk down like a thirsty whore",
      "Gonna let you ruin my cunt and my ass",
      "Sucking your balls empty into my belly",
      "Gonna ride your cock till I fucking squirt",
      "Spreading my cunt wide open for your dick",
      "Gonna drink your fat fucking load down",
      "Gagging on your cock with cum dripping out",
      "Gonna pump your dick dry with my mouth",
      "Clenching my asshole around your fat cock",
      "Gonna choke on your nut like a good slut",
      "Drooling cum all down my fucking chin",
      "Gonna stuff both my holes with your cock",
      "Sucking your fat dick to the fucking root",
      "Gonna milk your cock with my cunt walls",
      "Gargling your spunk in the back of my throat",
      "Gonna let you breed my fertile cunt",
      "Bobbing my whore mouth on your dick",
      "Gonna drain your aching fucking balls",
      "Licking your cum off my own tits",
      "Gonna take your cock deeper you sick fuck",
      "Squeezing your nut out with my cunt",
      "Gonna gag myself stupid on your dick",
      "Riding your fat cock like a cheap whore",
      "Gonna swallow your cum like it's fucking air",
      "Drooling all over your swollen fucking balls",
      "Gonna let you fill my cunt to the brim",
      "Choking down your cock and your nut both",
      "Gonna fuck your fat dick with my throat",
      "Slurping your jizz out of my own cunt",
      "Gonna beg you to wreck my fucking holes",
      "Sucking your cock with cum-glazed lips",
      "Gonna take your whole load down my throat",
      "Grinding my dripping cunt on your dick",
      "Gonna milk your prick dry you nasty fuck",
      "Gagging on your fat cock for your cum",
      "Gonna spread my asshole for your dick",
      "Drinking your nut straight from your balls",
      "Gonna ride your cock raw and filthy",
      "Choking on your dick till my eyes water",
      "Gonna swallow your fat fucking spunk",
      "Slobbering on your cockhead like a slut",
      "Gonna stuff your cum-loaded cock in me",
      "Squirting my cunt all over your balls",
      "Gonna nurse on your fat fucking sack",
      "Gulping down every rope of your jizz",
      "Gonna let you breed me like a bitch",
      "Sucking your dick down to your balls",
      "Gonna drain your fat nut into my gut",
      "Clenching my wet cunt to milk you dry",
      "Gonna gag on your prick you dirty fuck",
      "Drooling spit and cum off your shaft",
      "Gonna take your dick in every fucking hole",
      "Choking your fat cock down my throat",
      "Gonna swallow your cum and beg for more",
      "Riding your dick till my cunt's raw",
      "Gonna milk your throbbing cock with my mouth",
      "Spitting and gagging on your fat dick",
      "Gonna let you nut deep in my cunt",
      "Sucking the spunk right out of your balls",
      "Gonna fuck you dry with my greedy cunt",
      "Deepthroating your cock you filthy fuck",
      "Gonna gulp your fat load down my throat",
      "Drooling cum down my tits for you",
      "Gonna take your cock balls-deep again",
      "Clenching my asshole tight on your dick",
      "Gonna milk your nuts empty into me",
      "Choking on your fat cock just for you",
      "Gonna swallow your dick to the fucking hilt",
      "Riding your prick like a cock-drunk whore",
      "Gonna drink your jizz down like a slut",
      "Slurping your fat balls clean of cum",
      "Gonna let you stretch my tight cunt out",
      "Gagging my throat raw on your fat dick",
      "Gonna breed my cunt with your hot nut",
      "Drooling all over your cock and your sack",
      "Gonna pump your fat load out with my throat",
      "Squeezing your cum out with my cunt walls",
      "Gonna choke and gag down all your spunk",
      "Sucking your cock like a fucking animal",
      "Gonna take your nut up my dirty asshole",
      "Riding your dick till you flood my cunt",
      "Gonna milk your fat prick dry you fuck",
      "Drooling cum off my chin just for you",
      "Gonna swallow your whole fucking sack-load",
      "Choking down your cock you nasty fuck",
      "Gonna let you wreck my throat and my cunt",
      "Keeping your fat cock buried in my throat"
    ]
  }
}
```

> **Style note (important):** these are aimed STRAIGHT AT THE USER — "Gonna fuck **you** dry",
> "Sucking the nut from **your** balls" — first-person, second-person target, present/"gonna"
> tense, and there are 120 of them so repetition is rare. When generating a custom sexual set
> (choice B), keep that same direct-to-the-user voice and aim for 100+ phrases unless the user
> asks otherwise.

---

## 🧹 SAFE / PROFESSIONAL set (if you want something tame)

For anyone who wants the feature without the filth. Paste as `verbs` with `"mode": "replace"`.

```json
{
  "spinnerVerbs": {
    "mode": "replace",
    "verbs": [
      "Cooking up a fix",
      "Wrangling the code",
      "Chasing the bug down",
      "Wiring it together",
      "Sharpening the logic",
      "Untangling the mess",
      "Reticulating splines",
      "Crunching the numbers",
      "Polishing the edges",
      "Hammering it into shape",
      "Tracing the call stack",
      "Stitching the pieces up",
      "Greasing the gears",
      "Threading the needle",
      "Buttoning it up"
    ]
  }
}
```

---

## ✍️ MANUAL WAY (no AI — do it yourself)

1. Open (or create) `./.claude/settings.json` in your project (or `~/.claude/settings.json` for
   everywhere).
2. If it's a brand-new empty file, paste one of the JSON blocks above as the whole file.
3. If it already has stuff in it, add just the `"spinnerVerbs": { ... }` key alongside the
   existing keys (mind the commas — it's still one JSON object).
4. Save. **Fully close and reopen the CLI.**
5. Watch the spinner — it should now flash your phrases.

---

## 🔧 TROUBLESHOOTING

- **Nothing changed** → You didn't restart. Settings load at startup. Close the CLI completely
  and reopen it.
- **Still nothing after restart** →
  - Make sure you edited the settings file the CLI actually reads (project `./.claude/settings.json`
    when you launch from that project, or `~/.claude/settings.json` for global).
  - Your CLI build may be **too old** to support `spinnerVerbs`. Update the CLI, then retry.
    (Quick check on a Unix-y shell: find your CLI binary and grep it —
    `grep -a -o "spinnerVerbs" /path/to/cli-binary` — if it prints `spinnerVerbs`, your build
    supports it.)
- **The whole CLI errors / settings ignored** → Your `settings.json` is probably invalid JSON
  (a missing or extra comma). Validate it: `node -e "require('./.claude/settings.json')"` — it
  prints nothing if valid, an error if broken. Fix the JSON.
- **Want the stock words back** → set `"mode": "append"` (mixes yours with defaults) or delete
  the whole `spinnerVerbs` key.

---

*Drop this file in any project root, hand it to the CLI, answer the one question — done.* 🖤
