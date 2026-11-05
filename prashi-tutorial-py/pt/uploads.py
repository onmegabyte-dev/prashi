"""File uploads. Images are public; study material is private (served only through an authorised route)."""
import os
import re
import secrets
from pathlib import Path

from werkzeug.exceptions import RequestEntityTooLarge

from .db import ROOT

PUBLIC_DIR = ROOT / 'uploads' / 'public'
PRIVATE_DIR = ROOT / 'storage' / 'private'
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE = 20 * 1024 * 1024
MAX_FILES = 5

# What an image file must start with, so a renamed .exe can't pass as .jpg.
_MAGIC = {
    'jpg': lambda b: b[:3] == b'\xff\xd8\xff',
    'png': lambda b: b[:4] == b'\x89PNG',
    'gif': lambda b: b[:4] == b'GIF8',
    'webp': lambda b: b[:4] == b'RIFF' and b[8:12] == b'WEBP',
}
_IMAGE_EXT = {'.jpg': 'jpg', '.jpeg': 'jpg', '.png': 'png', '.gif': 'gif', '.webp': 'webp'}
_DOC_EXT = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.txt', '.zip', '.jpg', '.jpeg', '.png']


class UploadedFile:
    """An uploaded file held in memory (fieldname, originalname, buffer, size)."""
    def __init__(self, fieldname, originalname, buffer):
        self.fieldname, self.originalname, self.buffer, self.size = fieldname, originalname, buffer, len(buffer)


class UploadError(Exception):
    pass


def read_uploads(request, accept=None):
    """Reads files from a multipart request. Returns (files, error_message).
    accept: a field name to accept (None = any). Mirrors the limits of the Node version: 20 MB per file, 5 files."""
    try:
        files = []
        for field in request.files:
            for f in request.files.getlist(field):
                if accept and field != accept:
                    return [], 'The upload failed. Please try again.'
                data = f.read(MAX_FILE + 1)
                if len(data) > MAX_FILE:
                    return [], 'LIMIT_FILE_SIZE'
                if f.filename:
                    files.append(UploadedFile(field, f.filename, data))
        if len(files) > MAX_FILES:
            return [], 'The upload failed. Please try again.'
        return files, ''
    except RequestEntityTooLarge:
        return [], 'LIMIT_FILE_SIZE'


def _rand():
    return secrets.token_hex(16)


def save_image(file, directory=None):
    """Saves a public image. Returns the stored file name, or raises UploadError with a plain-English message."""
    directory = directory or PUBLIC_DIR
    ext = Path(file.originalname).suffix.lower()
    kind = _IMAGE_EXT.get(ext)
    if not kind:
        raise UploadError('Images must be JPG, PNG, GIF or WebP.')
    if file.size > 5 * 1024 * 1024:
        raise UploadError('Images must be under 5 MB.')
    if not _MAGIC[kind](file.buffer):
        raise UploadError('That file is not a real image.')
    name = _rand() + '.' + kind
    (directory / name).write_bytes(file.buffer)
    return name


def save_image_private(file):
    """Same checks, but the picture is kept private (served only through a checked route). Used for student photos."""
    return save_image(file, PRIVATE_DIR)


def save_document(file):
    """Saves a private document. Returns (stored, original)."""
    ext = Path(file.originalname).suffix.lower()
    if ext not in _DOC_EXT:
        raise UploadError('Allowed files: PDF, Word, PowerPoint, Excel, text, ZIP, JPG, PNG.')
    stored = _rand() + ext
    (PRIVATE_DIR / stored).write_bytes(file.buffer)
    original = re.sub(r'[^\w.\- ]', '_', os.path.basename(file.originalname))[:120]
    return stored, original


def safe_name(n):
    """Blocks '../' tricks: only names this module itself generated are accepted."""
    return n if re.fullmatch(r'[a-f0-9]{32}\.[a-z0-9]{2,5}', n or '') else None


def remove_public(n):
    if safe_name(n):
        (PUBLIC_DIR / n).unlink(missing_ok=True)


def remove_private(n):
    if safe_name(n):
        (PRIVATE_DIR / n).unlink(missing_ok=True)
