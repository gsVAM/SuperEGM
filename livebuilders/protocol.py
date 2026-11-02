"""Bounded, checksummed objects shared by the laptop and sandbox worker."""
import hashlib
import io
import json
import os
import re
import tarfile
from pathlib import Path, PurePosixPath

MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 20000
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_NAME_JSON_BYTES = 512
SECRET = re.compile(rb"(?:sk-ant-[A-Za-z0-9_-]{12,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
EXCLUDED = {'.git', '.aws', '.ssh', '.claude', '.codex', 'node_modules', '__pycache__', '.venv', 'dist', 'coverage'}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    try:
        name.encode('utf-8')
    except UnicodeEncodeError:
        raise ValueError('Path is not valid UTF-8') from None
    if len(encoded(name)) > MAX_NAME_JSON_BYTES:
        raise ValueError('Path exceeds 512 serialized bytes')
    path = PurePosixPath(name)
    devices = {'CON', 'PRN', 'AUX', 'NUL', *(f'{prefix}{n}' for prefix in ('COM', 'LPT') for n in '123456789¹²³')}
    windows_alias = any(p.endswith((' ', '.')) or p.split('.')[0].upper() in devices for p in path.parts)
    if not name or path.is_absolute() or '..' in path.parts or path.as_posix() != name or '\\' in name or ':' in name or any(ord(c) < 32 for c in name) or windows_alias or name == '.':
        raise ValueError('Unsafe artifact path')
    return name


def prefixes(owner, run_id):
    if not re.fullmatch(r'[0-9a-f]{24}', owner) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', run_id):
        raise ValueError('Invalid owner or run ID')
    return tuple(f'{kind}/livebuilders/{owner}/{run_id}/' for kind in ('inputs', 'runs'))


def scan(data):
    if SECRET.search(data):
        raise ValueError('Credential pattern detected; object was not published')


def redacted(text):
    return SECRET.sub(b'[REDACTED]', text.encode()).decode(errors='replace')


def excluded(parts):
    return any(p in EXCLUDED or p == '.env' or p.startswith('.env.') or p.endswith(('.pem', '.key')) for p in parts)


def bundle(directory):
    root = Path(directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Source must be a directory')
    result = io.BytesIO()
    total = count = 0
    with tarfile.open(fileobj=result, mode='w:gz') as archive:
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not excluded((Path(current) / d).relative_to(root).parts))
            for name in dirs + sorted(files):
                file = Path(current) / name
                relative = file.relative_to(root)
                if excluded(relative.parts):
                    continue
                if file.is_symlink():
                    raise ValueError('Source symlinks are not supported')
                if file.is_dir():
                    continue
                if not file.is_file():
                    raise ValueError('Source must contain regular files only')
                count += 1
                total += file.stat().st_size
                if count > MAX_FILES or total > MAX_BYTES:
                    raise ValueError('Source bundle exceeds limit')
                data = file.read_bytes()
                scan(data)
                info = tarfile.TarInfo(safe_name(relative.as_posix()))
                info.size = len(data)
                info.mode = 0o755 if file.stat().st_mode & 0o111 else 0o644
                archive.addfile(info, io.BytesIO(data))
    return result.getvalue()


def unpack(data, directory):
    root = Path(directory)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    seen = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            name = safe_name(member.name)
            if name in seen or not member.isfile() or len(seen) >= MAX_FILES:
                raise ValueError('Duplicate or non-regular archive member')
            seen.add(name)
            total += member.size
            if total > MAX_BYTES:
                raise ValueError('Expanded source exceeds limit')
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            with file.open('xb') as output:
                output.write(archive.extractfile(member).read())
            file.chmod(0o755 if member.mode & 0o111 else 0o644)


def checked(data, metadata):
    if len(data) != metadata['size'] or digest(data) != metadata['sha256']:
        raise ValueError('Artifact checksum or size mismatch')
    return data


def output_entries(manifest, output_prefix):
    if manifest.get('schema') != 1 or manifest.get('status') not in ('passed', 'failed', 'cancelled', 'timed_out'):
        raise ValueError('No valid final manifest')
    entries = manifest.get('files', [])
    seen = set()
    total = 0
    if not entries or len(entries) > MAX_FILES:
        raise ValueError('Invalid artifact count')
    for item in entries:
        name = safe_name(item['name'])
        if name == 'manifest.json' or name in seen or item['key'] != output_prefix + 'out/' + name:
            raise ValueError('Duplicate or cross-run artifact')
        seen.add(name)
        if type(item['size']) is not int or item['size'] < 0 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid artifact metadata')
        total += item['size']
    if total > MAX_BYTES:
        raise ValueError('Output exceeds limit')
    return entries


class Store:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket

    def get(self, key, limit=MAX_BYTES + 20 * 1024 * 1024):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            data = response['Body'].read(limit + 1)
        finally:
            response['Body'].close()
        if len(data) > limit:
            raise ValueError('S3 object exceeds limit')
        return data, response['ETag']

    def json(self, key):
        data, etag = self.get(key, MAX_MANIFEST_BYTES if key.endswith('/manifest.json') else 1024 * 1024)
        return json.loads(data), etag

    def put(self, key, data, **conditions):
        return self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption='AES256', **conditions)

    def put_json(self, key, value, **conditions):
        data = encoded(value)
        if key.endswith('/manifest.json') and len(data) > MAX_MANIFEST_BYTES:
            raise ValueError('Manifest exceeds 32 MiB')
        return self.put(key, data, **conditions)

    def optional(self, key):
        try:
            return self.json(key)[0]
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None
            raise
