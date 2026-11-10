"""Putting fonts into the user's font folder and taking them out again.

Everything here blocks on the disk, so Home Assistant calls it through an
executor. Installs and deletes hold a lock and stage under their own name: two
uploads can reach the same id at once, and one would otherwise remove the file
the other had just put there.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import shutil
import tempfile
import threading
import zipfile
import zlib
from typing import Final

from .const import (
    FONT_EXTENSIONS,
    MAX_ARCHIVE_MEMBERS,
    MAX_ARCHIVE_BYTES,
    MAX_FONT_BYTES,
    WEBFONT_EXTENSIONS,
)
from .fonts import (
    decode_webfont,
    display_name,
    font_id,
    installed_font_files,
)

_LOGGER = logging.getLogger(__name__)

_INSTALL_LOCK: Final = threading.Lock()

#: A digest of the user's font folder, so a consumer that caches by font id can
#: tell that the file behind an id was replaced. Empty until the folder is read.
_revision = ""


class FontInstallError(ValueError):
    """A file that is not a font this can install.

    Carries a ``code`` the panel translates, so a refusal reads in the user's
    language rather than in the sentence this module happens to write.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def revision() -> str:
    """The digest of the user's font folder as it was last read."""
    return _revision


def refresh_revision(user_dir: str | None) -> str:
    """Read the user's font folder and remember what it looks like. Blocking.

    Taken from the name, size and modification time of each file rather than
    from their contents: a folder of forty fonts is read on every install, and
    the question is only whether anything about it changed.
    """
    global _revision
    parts = []
    for path in sorted(installed_font_files(user_dir or "")):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        parts.append(f"{os.path.basename(path)}:{stat.st_size}:{stat.st_mtime_ns}")
    _revision = hashlib.md5("|".join(parts).encode()).hexdigest()[:8] if parts else ""
    return _revision


def _readable_font(path: str) -> str:
    """The display name of the font at *path*, or raise ``FontInstallError``.

    A web font is decoded into a scratch ``.ttf`` first, because the question
    is whether Pillow will be able to draw with it once the cache has run --
    not whether the compressed file itself opens.
    """
    probe = path
    with tempfile.TemporaryDirectory() as scratch:
        if path.lower().endswith(WEBFONT_EXTENSIONS):
            probe = os.path.join(scratch, "probe.ttf")
            if not decode_webfont(path, probe):
                raise FontInstallError("unreadable", "this web font cannot be decoded")
        name = display_name(probe)
    if not name:
        raise FontInstallError("unreadable", "this file is not a font Pillow can read")
    return name


def font_filename(filename: str, *, strip_axes: bool = True) -> str:
    """The plain file name a font will be stored under.

    A variable font arrives as ``Roboto[wdth,wght].ttf``; the axis block would
    become part of its id and then part of every address naming it, so it is
    cut. Pass ``strip_axes=False`` where the id already in use must be kept.
    """
    name = os.path.basename(str(filename or "").strip().replace("\\", "/"))
    if not strip_axes:
        return name
    stem, extension = os.path.splitext(name)
    bracket = stem.find("[")
    if bracket > 0 and stem.endswith("]"):
        stem = stem[:bracket].rstrip("-_ ")
    return f"{stem}{extension}" if stem else name


def install_font(
    user_dir: str, filename: str, data: bytes | None = None, *,
    source_path: str | None = None,
    replace: bool = True, keep_filename: bool = False,
) -> dict[str, object]:
    """Write an uploaded font into the user's font folder. Blocking.

    The font is *data*, or the file at *source_path*, which is moved rather
    than copied and so should already sit in *user_dir*: a font of a hundred
    megabytes is then never held in memory, nor written twice.

    The file keeps its own name, so its id stays the one consumers carry. An id
    one of the user's own fonts holds replaces that file, whatever extension it
    had, because uploading an updated font means exactly that; pass
    ``replace=False`` where that is not wanted.

    A ``.ttc`` collection is split into its fonts instead, see
    :func:`install_font_collection`, and answers the way an archive does.

    Returns ``{"id", "name", "replaced"}``.
    """
    name = font_filename(filename, strip_axes=not keep_filename)
    extension = os.path.splitext(name)[1].lower()
    if extension == ".ttc":
        try:
            return install_font_collection(
                user_dir, name, data, source_path=source_path, replace=replace)
        finally:
            if source_path and os.path.exists(source_path):
                os.remove(source_path)
    if extension not in FONT_EXTENSIONS + WEBFONT_EXTENSIONS:
        raise FontInstallError("bad_type", f"{name!r} is not a font file")
    fid = font_id(name)
    if not fid or name.startswith("."):
        raise FontInstallError("bad_name", f"{name!r} is not a usable font name")

    os.makedirs(user_dir, exist_ok=True)
    # Staged beside its destination, then proved and moved: a half-written or
    # unreadable file never sits in the folder the picker reads. The staging
    # name is this write's own, so two of them cannot land on one file.
    handle_fd, staged = tempfile.mkstemp(
        dir=user_dir, prefix=f".{fid}.incoming", suffix=extension)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
            if source_path is None:
                handle.write(data or b"")
        if source_path is not None:
            os.replace(source_path, staged)
        if not os.path.getsize(staged):
            raise FontInstallError("empty", "the file is empty")
        display = _readable_font(staged)
        with _INSTALL_LOCK:
            existing = [other for other in installed_font_files(user_dir)
                        if font_id(other) == fid]
            if existing and not replace:
                raise FontInstallError("exists", f"a font named {fid!r} is installed")
            for other in existing:
                os.remove(other)
            os.replace(staged, os.path.join(user_dir, name))
        replaced = bool(existing)
    finally:
        if os.path.exists(staged):
            os.remove(staged)
    return {"id": fid, "name": display, "replaced": replaced}


def _face_stem(font, fallback: str) -> str:
    """A file name stem for one font out of a collection.

    Its PostScript name is unique within a family and already file-safe by its
    own rules; anything else is replaced so it cannot name a path.
    """
    try:
        raw = font["name"].getDebugName(6) or ""
    except Exception:  # noqa: BLE001 - a font without names still gets a file
        raw = ""
    stem = re.sub(r"[^A-Za-z0-9 _.-]+", "-", raw).strip(" .-")
    return stem or fallback


def _hidden_font(font) -> bool:
    """Whether a font is one its maker hid from users.

    Apple names the fonts its own interface uses with a leading dot --
    ``.Apple Color Emoji UI`` beside Apple Color Emoji -- and lists none of
    them in its Font Book. They are near copies of the font next to them, not
    a style anyone picks.
    """
    try:
        names = [font["name"].getDebugName(i) or "" for i in (16, 1, 6)]
    except Exception:  # noqa: BLE001 - a font without names is not hidden
        return False
    return any(name.startswith(".") for name in names)


def split_collection(
    filename: str, source: bytes | str, scratch: str,
) -> list[tuple[str, str]]:
    """The fonts inside a ``.ttc`` collection, each written into *scratch*.

    *source* is the collection's bytes or its path; a path is read as needed
    rather than whole. Answers ``[(file name, path in scratch)]``.

    A browser cannot load a collection as a web font, so kept whole it could be
    listed but never drawn, picked for the interface, or used in a theme.
    Split, every font in it is an ordinary font like any other -- except the
    ones its maker hid (see :func:`_hidden_font`), which are left out.
    """
    from fontTools.ttLib import TTCollection  # noqa: PLC0415 - only needed here

    base = os.path.splitext(os.path.basename(filename))[0] or "font"
    try:
        collection = TTCollection(
            io.BytesIO(source) if isinstance(source, bytes) else source)
    except Exception as err:  # noqa: BLE001 - anything unparsable is refused alike
        raise FontInstallError("unreadable", "this collection cannot be read") from err

    files: list[tuple[str, str]] = []
    seen: set[str] = set()
    with collection:
        for index, font in enumerate(collection.fonts, start=1):
            if _hidden_font(font):
                continue
            extension = ".otf" if "CFF " in font or "CFF2" in font else ".ttf"
            # The first font keeps the collection's own name, and with it the
            # id the collection was known by: Pillow opens a collection at its
            # first font, so whatever resolved that id keeps drawing the same.
            stem = base if index == 1 else _face_stem(font, f"{base}-{index}")
            if stem.lower() in seen:
                stem = f"{stem}-{index}"
            seen.add(stem.lower())
            path = os.path.join(scratch, f"{index}{extension}")
            try:
                font.save(path)
            except Exception as err:  # noqa: BLE001 - one bad face must not lose the rest
                _LOGGER.warning(
                    "Could not take font %d out of %s: %s", index, filename, err)
                continue
            files.append((f"{stem}{extension}", path))
    if not files:
        raise FontInstallError("no_fonts", "this collection holds no fonts")
    return files


def install_font_collection(
    user_dir: str, filename: str, data: bytes | None = None, *,
    source_path: str | None = None, replace: bool = True,
) -> dict[str, object]:
    """Install every font in a ``.ttc`` collection as its own file. Blocking.

    The collection is *data* or the file at *source_path*, which is only read.
    Answers the way :func:`install_font_archive` does, since a collection is a
    family in one file just as an archive is a family in one zip.
    """
    os.makedirs(user_dir, exist_ok=True)
    installed: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(dir=user_dir, prefix=".split-") as scratch:
        source = source_path if source_path is not None else (data or b"")
        for name, face in split_collection(filename, source, scratch):
            try:
                installed.append(install_font(
                    user_dir, name, source_path=face, replace=replace))
            except FontInstallError as err:
                skipped.append({"name": name, "code": err.code})
    return {
        "archive": os.path.basename(str(filename or "").replace("\\", "/")),
        "installed": installed,
        "skipped": skipped,
    }


def sweep_staging(user_dir: str) -> None:
    """Remove what an upload cut short left behind. Blocking.

    Uploads stream into hidden files and directories beside the fonts; a
    restart in the middle of one would otherwise leave them there for good.
    """
    if not os.path.isdir(user_dir):
        return
    for name in os.listdir(user_dir):
        path = os.path.join(user_dir, name)
        if name.startswith((".upload-", ".unzip-")) or ".incoming" in name:
            if os.path.isfile(path):
                os.remove(path)
        elif name.startswith(".split-") and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


def split_installed_collections(user_dir: str) -> list[str]:
    """Split every ``.ttc`` already in the folder; the files that were. Blocking.

    For collections installed before uploads were split. The collection is
    moved aside first: its own id is often that of its regular font, which
    would otherwise be refused as already installed and then lost with it. It
    goes only once every font in it is in the folder, and comes back if not.
    """
    done: list[str] = []
    # A split cut short -- by a restart, say -- leaves its collection aside.
    for leftover in os.listdir(user_dir) if os.path.isdir(user_dir) else []:
        if leftover.startswith(".") and leftover.endswith(".ttc.splitting"):
            original = os.path.join(user_dir, leftover[1:-len(".splitting")])
            if not os.path.exists(original):
                os.replace(os.path.join(user_dir, leftover), original)
    for path in installed_font_files(user_dir):
        if not path.lower().endswith(".ttc"):
            continue
        name = os.path.basename(path)
        aside = os.path.join(user_dir, f".{name}.splitting")
        try:
            os.replace(path, aside)
            result = install_font_collection(
                user_dir, name, source_path=aside, replace=False)
        except (FontInstallError, OSError) as err:
            _LOGGER.warning("Could not split %s: %s", name, err)
            if os.path.exists(aside):
                os.replace(aside, path)
            continue
        if any(item["code"] != "exists" for item in result["skipped"]):
            _LOGGER.warning("Kept %s: not every font in it could be installed", name)
            os.replace(aside, path)
            continue
        os.remove(aside)
        done.append(name)
    return done


def _deletable_font_id(font: str) -> str:
    """*font* as the id it names, or ``ValueError`` when it names no font."""
    wanted = str(font).strip().lower()
    if not wanted or wanted in {".", ".."} or os.path.basename(wanted) != wanted:
        raise ValueError(f"{font!r} is not a font that may be deleted")
    return wanted


def delete_fonts(user_dir: str, fonts: list[str]) -> list[str]:
    """Remove several of the user's fonts; the ids that actually went.

    Every extension of an id goes, since the file behind it may be the
    ``.ttf`` or the ``.woff2`` it was uploaded as; the decoded copy in the
    web-font cache follows its source on the next listing. Every id is
    validated before any file is removed, and the batch holds the install
    lock, so a family is never half removed.
    """
    wanted = [_deletable_font_id(font) for font in fonts]
    removed: list[str] = []
    with _INSTALL_LOCK:
        paths_by_id: dict[str, list[str]] = {}
        for path in installed_font_files(user_dir):
            paths_by_id.setdefault(font_id(path), []).append(path)

        for wanted_id in dict.fromkeys(wanted):
            paths = paths_by_id.get(wanted_id, [])
            for path in paths:
                os.remove(path)
            if paths:
                removed.append(wanted_id)
    return removed



def _archive_font_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """The members of *archive* worth trying to install, in a stable order.

    Everything that is not a font file -- the licence, the readme, the folder
    entries, the resource forks a Mac archiver leaves behind -- is dropped here
    rather than counted as something that failed.
    """
    members = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = info.filename.replace("\\", "/").split("/")
        # A leading dot hides a file; ".." only walks up, and the name is taken
        # by basename anyway, so it cannot reach outside the folder.
        if any(p.startswith(".") and p.strip(".") for p in parts):
            continue
        if "__MACOSX" in parts:
            continue
        if parts[-1].lower().endswith(FONT_EXTENSIONS + WEBFONT_EXTENSIONS):
            members.append(info)
    return sorted(members, key=lambda i: i.filename.lower())


def install_font_archive(
    user_dir: str,
    filename: str,
    data: bytes | None = None,
    *,
    source_path: str | None = None,
    max_member_bytes: int = MAX_FONT_BYTES,
    max_total_bytes: int = MAX_ARCHIVE_BYTES,
    max_members: int = MAX_ARCHIVE_MEMBERS,
) -> dict[str, object]:
    """Install every font inside an uploaded zip. Blocking.

    A font archive is what a foundry actually hands out, so the whole family
    goes in at once and each member lands exactly as a single upload of that
    file would: its own name, its own id, nothing to unpack by hand.

    One member failing is not the archive failing -- it is listed in ``skipped``
    and the rest still install. An archive where nothing installs returns an
    empty ``installed`` rather than raising, so the caller can say which file
    failed and why; only an archive that cannot be opened, holds no fonts at
    all, or is implausibly large is refused outright.

    The archive is *data* or the file at *source_path*, which is only read;
    each member is unpacked to a file rather than into memory.
    """
    try:
        archive = zipfile.ZipFile(
            source_path if source_path is not None else io.BytesIO(data or b""))
    except (zipfile.BadZipFile, OSError) as err:
        raise FontInstallError("bad_archive", "this file is not a readable zip") from err

    with archive:
        members = _archive_font_members(archive)
        if not members:
            raise FontInstallError("no_fonts", "this archive holds no font files")
        if len(members) > max_members:
            raise FontInstallError(
                "archive_too_large", "this archive holds too many fonts")
        if sum(i.file_size for i in members) > max_total_bytes:
            raise FontInstallError(
                "archive_too_large", "the fonts in this archive are too large")

        installed: list[dict[str, object]] = []
        skipped: list[dict[str, str]] = []
        seen: set[str] = set()
        unpacked = ""
        for info in members:
            name = font_filename(info.filename)
            fid = font_id(name)
            if fid in seen:
                continue
            seen.add(fid)
            if info.file_size > max_member_bytes:
                skipped.append({"name": name, "code": "too_large"})
                continue
            try:
                os.makedirs(user_dir, exist_ok=True)
                handle_fd, unpacked = tempfile.mkstemp(dir=user_dir, prefix=".unzip-")
                with os.fdopen(handle_fd, "wb") as out, archive.open(info) as member:
                    shutil.copyfileobj(member, out, 1024 * 1024)
                result = install_font(user_dir, name, source_path=unpacked)
                if "installed" in result:
                    # A collection inside the archive: its fonts count one by one.
                    installed.extend(result["installed"])
                    skipped.extend(result["skipped"])
                else:
                    installed.append(result)
            except FontInstallError as err:
                skipped.append({"name": name, "code": err.code})
            except (zipfile.BadZipFile, RuntimeError, zlib.error, EOFError) as err:
                # A bad checksum or a member needing a password: the archive
                # opened, this one file cannot be read out of it.
                _LOGGER.warning("Could not read %s out of an archive: %s", name, err)
                skipped.append({"name": name, "code": "unreadable"})
            except OSError as err:
                _LOGGER.warning("Could not write %s from an archive: %s", name, err)
                skipped.append({"name": name, "code": "write_failed"})
            finally:
                if unpacked and os.path.exists(unpacked):
                    os.remove(unpacked)
                unpacked = ""

    return {
        "archive": os.path.basename(str(filename or "").replace("\\", "/")),
        "installed": installed,
        "skipped": skipped,
    }
