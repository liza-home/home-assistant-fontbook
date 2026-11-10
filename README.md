# Fontbook for Home Assistant

Fontbook lets you add your own fonts to Home Assistant and use them in your
interface, themes and dashboard cards. Its Fontbook sidebar page lets you
preview fonts, explore their characters and choose how Home Assistant's text
looks.

## What you can do

- Upload TTF, OTF, TTC, WOFF or WOFF2 fonts, or a ZIP containing a font family.
  Font collections are split into individual faces.
- Browse font families and styles, preview them at different sizes, and
  explore and copy their characters. Colour emoji fonts show the pictures
  stored in the font, including flags and skin tones.
- Choose a font for Home Assistant's interface and adjust its text size from
  80% to 200%, with a preview before applying it.
- Use installed fonts in your own themes and dashboard cards.

Fonts are stored in `config/www/fonts` and remain there if you remove
Fontbook. The Fontbook page is available to administrators.

## Installation

**Requires Home Assistant 2026.11.0 or newer.**

### Marketplace

Open Fontbook in the Home Assistant Marketplace:

[![Open Fontbook in the Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=liza-home&repository=home-assistant-fontbook&category=integration)

1. Open the link and install **Fontbook**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and add
   **Fontbook**.

### Manual installation

1. Download `fontbook_<version>.tgz` from the
   [latest release](https://github.com/liza-home/home-assistant-fontbook/releases/latest).
2. Extract the archive into `config/custom_components`. The result should be
   `config/custom_components/fontbook`.
3. Restart Home Assistant, then add **Fontbook** under **Settings → Devices &
   services → Add integration**.

## Using Fontbook

Open **Fontbook** in the sidebar, or visit `/fontbook`. Each user can hide the
sidebar item in their profile's sidebar editor.

In the **Library** tab, drop font files or a ZIP onto the page, or click the
drop zone to browse. Open a font to inspect its styles, metadata and
characters; use the trash button to remove an uploaded font. Fonts that come
with Home Assistant cannot be removed.

In the **Interface** tab, choose an installed font and text size. Reset the
settings to return to Home Assistant's defaults. These choices apply to devices
that open your Home Assistant instance. A theme that sets its own typography
takes precedence over the font selected in Fontbook.

### Using a font in a theme

Use the font's family name, for example:

```yaml
my_theme:
  ha-font-family-body: "Inter"
```

### Using a font in a dashboard card

For example, with the separately installed
[card-mod](https://github.com/thomasloven/lovelace-card-mod) integration:

```yaml
type: markdown
content: Hello
card_mod:
  style: |
    ha-card { font-family: "Inter"; }
```

## Removing Fontbook

Remove **Fontbook** under **Settings → Devices & services**, then uninstall it
from the Marketplace or remove `config/custom_components/fontbook` if installed
manually. Your fonts remain in `config/www/fonts`; delete them separately if
you no longer need them.

## Support

Report problems or suggestions in the
[issue tracker](https://github.com/liza-home/home-assistant-fontbook/issues).
