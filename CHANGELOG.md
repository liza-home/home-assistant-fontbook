# Changelog

Notable changes to Fontbook, described in terms of what they change for
someone using it. The development repository keeps a fuller log that also
covers internal work.

The format is based on Keep a Changelog. Versions are calendar versions:
`YYYY.MM.N`, where `N` counts the releases made in that month and starts at 1.

Each release starts with **⚠ Breaking changes**, if it has any: anything that
makes something you set up stop working or look different, each with a
**What to do:** line that says how to get it working again. Features that were
removed are always listed under **Removed**, new ones under **Added**.

## [2026.11.1] - 2026-11-09

The first release of Fontbook.

### Added

- A **Fontbook** page in the sidebar for administrators, at `/fontbook`. Each
  user can hide it in Home Assistant's own sidebar editor.
- **Add fonts** by dropping TTF, OTF, TTC, WOFF, WOFF2 or a ZIP of them onto
  the page. A ZIP is unpacked, and a `.ttc` collection is split into one font
  per style; fonts Apple hides from users, such as `.Apple Color Emoji UI`,
  are left out. Fonts of up to 256 MB are accepted, enough for a colour emoji
  font.
- **Browse your fonts**, each family drawn in itself with its name beneath. A
  symbol or emoji font shows characters it holds rather than empty boxes.
- **A page for each font**: a preview of A–Z, a–z and 0–9, every size, each
  style, what the font says about itself, and every character it holds —
  filterable by name, character or `U+` code, each one opening large with a
  Copy button. Colour emoji fonts such as Apple Color Emoji and Noto Color
  Emoji show the pictures stored in the font, flags and skin tones included,
  in every browser.
- **Remove** your own fonts with a red trash button, after confirming.
- **Draw Home Assistant in your font**, and scale its text from 80% to 200%,
  for every device, with a live preview first.
- **Use any font yourself** in a theme or a card by its family name, and from
  another integration through `hass.data["fontbook"]`.
- Fontbook's own icon on the integration page.
