/** The panel's stylesheet, as a string so the module graph needs no build step. */

export const PANEL_CSS = `
:host {
  display: block;
  background: var(--primary-background-color);
  font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
  min-height: 100vh;
}
/* Inside another panel: its page, its background and its height. */
:host([embedded]) {
  background: none;
  min-height: 0;
}
:host([embedded]) .wrap { padding: 0; }
.wrap {
  max-width: 920px;
  margin: 0 auto;
  padding: 16px 16px 48px;
  box-sizing: border-box;
}
/* A font's page has a character grid that is worth every column it can get. */
.wrap.is-wide { max-width: none; padding-inline: 24px; }
/* Shaped after Home Assistant's own hass-tabs-subpage toolbar, so the panel
   sits in the sidebar's colours rather than the app header's. */
.toolbar {
  height: var(--header-height, 56px);
  box-sizing: border-box;
  background-color: var(--sidebar-background-color, var(--card-background-color));
  color: var(--sidebar-text-color, var(--primary-text-color));
  border-bottom: 1px solid var(--divider-color);
  font-size: var(--ha-font-size-xl, 20px);
  font-weight: var(--ha-font-weight-normal, 400);
  position: sticky;
  top: 0;
  z-index: 2;
}
.toolbar-content {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 8px 12px;
  box-sizing: border-box;
}
/* Home Assistant's own rule for a heading that is read out but not drawn. */
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.toolbar-end {
  min-width: 48px;
  flex: 0 0 auto;
}
ha-icon-button.menu {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  color: var(--sidebar-icon-color, var(--primary-text-color));
  --mdc-icon-button-size: 48px;
}
ha-icon-button.menu svg { width: 24px; height: 24px; fill: currentColor; }
.hint {
  color: var(--secondary-text-color);
  font-size: 14px;
  margin: 0 0 16px;
}
.wrap > ha-card { margin-bottom: 16px; }

.family {
  border-top: 1px solid var(--divider-color, #e0e0e0);
  padding: 12px 0;
}
.family:first-of-type { border-top: 0; }
button.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 0;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  cursor: pointer;
  color: var(--primary-text-color);
  opacity: .75;
  line-height: 1;
}
button.icon svg { width: 24px; height: 24px; flex: none; fill: currentColor; }
button.icon:hover { background: rgba(127, 127, 127, .25); opacity: 1; }
button.icon:focus-visible { outline: 2px solid var(--primary-color); }

.toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  background: var(--primary-text-color);
  color: var(--card-background-color);
  padding: 10px 18px;
  border-radius: 6px;
  font-size: 14px;
  z-index: 10;
  max-width: 80vw;
}

.toast[hidden] {
  display: none;
}

dialog {
  border: 0;
  border-radius: 12px;
  padding: 20px;
  max-width: 440px;
  background: var(--card-background-color);
  color: var(--primary-text-color);
}
dialog::backdrop { background: rgba(0, 0, 0, .4); }
dialog h3 { margin: 0 0 8px; font-size: 18px; font-weight: 500; }
dialog p { margin: 0 0 16px; color: var(--secondary-text-color); font-size: 14px; }
dialog .actions { display: flex; justify-content: flex-end; gap: 8px; }
dialog ul { margin: 0 0 12px; padding-left: 20px; font-size: 14px; }
dialog li { margin-bottom: 4px; }
dialog .why { color: var(--secondary-text-color); font-size: 12px; display: block; }

.setting {
  display: grid;
  grid-template-columns: minmax(80px, 140px) 1fr;
  gap: 16px;
  align-items: center;
  padding: 8px 0;
}
.setting-label { color: var(--primary-text-color); }
@media (max-width: 600px) {
  .setting { grid-template-columns: 1fr; gap: 4px; }
}
.interface-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.interface-controls fonts-manager-dropdown {
  flex: 1 1 220px;
  min-width: 0;
}
.interface-controls ha-button { flex: 0 0 auto; }
.interface-controls ha-slider {
  flex: 1;
  min-width: 0;
}
.interface-controls output {
  min-width: 4ch;
  font-variant-numeric: tabular-nums;
  color: var(--secondary-text-color);
}

dl.info {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 16px;
  margin: 0 0 16px;
  font-size: 14px;
}
dl.info dt { color: var(--secondary-text-color); }
dl.info dd { margin: 0; word-break: break-word; }
dl.info a { color: var(--primary-color); }

/* A licence header runs to paragraphs, which would push the rest of the
   dialog off the screen, so it is folded until it is asked for. */
.clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.clamp.is-open { display: block; }
button.linkish {
  display: block;
  margin: 2px 0 0;
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  color: var(--primary-color);
  cursor: pointer;
}
.licence-link { margin-top: 2px; }
.tabs {
  flex: 1;
  min-width: 0;
}

.wrap { position: relative; }

#pick { display: none; }

.family { border-top: 1px solid var(--divider-color, #e0e0e0); }
.family:first-of-type { border-top: 0; }
.frow { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.frow.is-face { padding-inline-start: 24px; }
.specimen {
  flex: 1;
  min-width: 0;
  display: block;
  text-align: start;
  background: none;
  border: 0;
  padding: 4px 0;
  cursor: pointer;
  color: var(--primary-text-color);
  border-radius: 8px;
}
.specimen:hover { background: rgba(127, 127, 127, .08); }
.specimen:focus-visible { outline: 2px solid var(--primary-color); }
.specimen .line {
  display: block;
  font-size: 28px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.specimen.face .line { font-size: 20px; }
.specimen .who {
  display: block;
  font-size: 12px;
  color: var(--primary-text-color);
  opacity: .65;
  margin-top: 2px;
}
.count { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; }
.acts { display: flex; gap: 4px; }
.chevron.is-open svg { transform: rotate(180deg); }
.styles { border-top: 1px solid var(--divider-color, #e0e0e0); }

.mock { display: flex; gap: 0; border-radius: 12px; overflow: hidden; }
.mock-side {
  width: 160px;
  flex: none;
  padding: 12px 0;
  background: var(--card-background-color, #fff);
  border-inline-end: 1px solid var(--divider-color, #e0e0e0);
}
/* Sized the way Home Assistant sizes itself: every value derived from the
   scale variable, so the mock shows the real effect. */
.mock-brand { font-size: calc(18px * var(--ha-font-size-scale, 1)); padding: 8px 16px 16px; }
.mock-item {
  padding: 10px 16px;
  font-size: calc(14px * var(--ha-font-size-scale, 1));
  color: var(--secondary-text-color);
}
.mock-item.is-on { color: var(--primary-color); background: rgba(127, 127, 127, .08); }
.mock-main { flex: 1; min-width: 0; padding: 16px; background: rgba(127, 127, 127, .06); }
.mock-card {
  background: var(--card-background-color, #fff);
  border-radius: 12px;
  padding: 16px;
}
.mock-card h3 {
  margin: 0 0 8px;
  font-size: calc(20px * var(--ha-font-size-scale, 1));
  font-weight: 400;
}
.mock-card p { margin: 0 0 8px; font-size: calc(14px * var(--ha-font-size-scale, 1)); }
.mock-reading { font-size: calc(36px * var(--ha-font-size-scale, 1)); margin-bottom: 8px; }
.mock-card code { font-size: calc(13px * var(--ha-font-size-scale, 1)); }

.detail h4 {
  margin: 20px 0 8px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--secondary-text-color);
}
.detail .specimen-text {
  width: 100%;
  box-sizing: border-box;
}
.drop-line { display: flex; align-items: baseline; gap: 12px; padding: 4px 0; }
.drop-line .px {
  width: 64px;
  flex: none;
  font-size: 11px;
  color: var(--secondary-text-color);
}
.drop-line .line { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }

.detail-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
}
.detail-head h2 {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 24px;
  font-weight: 400;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
ha-icon-button.back svg { width: 24px; height: 24px; fill: currentColor; }
.detail h4:first-of-type { margin-top: 16px; }
.alphabet {
  font-size: 40px;
  line-height: 1.25;
  overflow-wrap: anywhere;
  margin-bottom: 8px;
}
.glyphs-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 20px 0 8px;
}
.glyphs-head h4 { margin: 0; flex: 1; }
.glyphs-head ha-input-search { flex: 0 1 320px; min-width: 200px; }
.detail h4 .count { margin-inline-start: 6px; text-transform: none; letter-spacing: 0; }
.glyphs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(56px, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}
button.glyph {
  aspect-ratio: 1;
  padding: 0;
  border: 1px solid var(--divider-color, rgba(127, 127, 127, .3));
  border-radius: 8px;
  background: rgba(127, 127, 127, .08);
  color: var(--primary-text-color);
  font-family: inherit;
  font-size: 26px;
  line-height: 1;
  overflow: hidden;
  cursor: pointer;
}
button.glyph img { width: 70%; height: 70%; object-fit: contain; vertical-align: middle; }
button.glyph:hover { border-color: var(--primary-color); }
button.glyph:focus-visible { outline: 2px solid var(--primary-color); }

dialog.glyph-dialog { width: min(360px, 90vw); }
.glyph-card {
  position: relative;
  padding: 16px;
  border-radius: 12px;
  background: rgba(127, 127, 127, .08);
}
.glyph-copy { position: absolute; top: 12px; inset-inline-end: 12px; }
.glyph-big {
  user-select: text;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  font-size: 140px;
  line-height: 1;
}
.glyph-big img { width: 160px; height: 160px; object-fit: contain; }
/* A bitmap emoji font's preview, drawn from its own pictures. */
.glyph-img { height: 1em; width: auto; vertical-align: -0.125em; }
.glyph-meta, .glyph-code {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}
.glyph-meta { color: var(--secondary-text-color); overflow-wrap: anywhere; }
.glyph-code {
  justify-content: flex-start;
  margin: 8px 0 16px;
  padding: 8px 16px;
  border-radius: 8px;
  background: rgba(127, 127, 127, .08);
}
#pick { display: none; }

.family { border-top-color: rgba(127, 127, 127, .35); }
.hint { opacity: .9; }

/* The promise the integration makes: what is meant to stay monospaced does. */
.mock-card code {
  font-family: var(--ha-font-family-code, "Roboto Mono", Consolas, monospace);
}
.dropzone {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 16px;
  padding: 36px 16px;
  border: 2px dashed rgba(127, 127, 127, .5);
  border-radius: 12px;
  background: none;
  color: var(--primary-text-color);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}
.dropzone svg { width: 22px; height: 22px; fill: var(--primary-color); flex: none; }
.dropzone:hover { border-color: var(--primary-color); background: rgba(127, 127, 127, .08); }
.dropzone:focus-visible { outline: 2px solid var(--primary-color); }
.dropzone.is-busy { opacity: .6; pointer-events: none; }

/* The window-wide drop stays silent until something is actually held over it. */
.dropzone.is-drop-over,
.wrap.is-drop-over .dropzone {
  border-color: var(--primary-color);
  border-style: dashed;
  background: rgba(127, 127, 127, .12);
}

.in-use {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid var(--primary-color);
  border-radius: 16px;
  color: var(--primary-color);
  font-size: 13px;
  white-space: nowrap;
}
.in-use svg { width: 16px; height: 16px; flex: none; fill: currentColor; }

button.icon.delete { color: var(--error-color, #db4437); opacity: 1; }
button.icon.delete:hover { background: rgba(219, 68, 55, .12); }


/* A row no longer reserves space for a name it was repeating. */
.frow { padding: 2px 0; }
.specimen { padding: 2px 0; }
.frow.is-face { padding-inline-start: 24px; }
`;
