# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the App client (spec section 11).

"""superegm builder-token: a one-hour installation token of the builder App on stdout, minted over
`urllib` from an RS256 JWT `openssl` signs with the key file `builder.app.private_key_env` names;
read-only, no run card. `doctor` and `launch` read the App through the same client."""

import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import superegm as core

WRITES = frozenset()  # builder-token writes nothing
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
API = "https://api.github.com"


def register(subparsers):
  p = core.add_parser(subparsers, "builder-token", "print a one-hour token of the builder App (a read: no run card)",
                      runcard=False)
  p.add_argument("--repo", help="owner/name (default: the config's)")
  p.add_argument("--app-id", dest="app_id", type=int, help="the App's id (default: builder.app.app_id)")
  p.add_argument("--key-env", dest="key_env", help="the variable naming the key file (default: builder.app.private_key_env)")
  p.add_argument("--openssl", help="the openssl to sign with (default: the one on PATH)")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    print(token(args))
    return 0
  except core.HandoffError as error:
    raise core.HandoffError(f"builder-token: {error}") from None


def token(args) -> str:
  """The token under the flags; a flag absent is read from the config of the working tree (the
  per-launch script passes all three, so no config is read at mint time)."""
  repo, app_id, env = args.repo, args.app_id, args.key_env
  if not (repo and app_id and env):
    config = core.load_config(core.git_toplevel(Path.cwd()))
    app = config["builder"]["app"]
    if app is None and not (app_id and env):
      raise core.HandoffError("builder.app is null: set it in .superegm/config.json or pass --app-id and --key-env")
    repo, app_id, env = repo or config["repo"], app_id or app["app_id"], env or app["private_key_env"]
  return mint(repo, app_id, key_path(env), args.openssl or tool("openssl"))


def key_path(env: str) -> Path:
  """The key file the variable `env` names, refused unless it is a readable file."""
  value = os.environ.get(env)
  if not value:
    raise core.HandoffError(f"{env} is not set")
  path = Path(value)
  if not path.is_file() or not os.access(path, os.R_OK):
    raise core.HandoffError(f"{env} names {value}, which is not a readable file")
  return path


def tool(name: str) -> str:
  """The absolute path of `name` on this machine's PATH, refused when there is none."""
  found = shutil.which(name)
  if not found:
    raise core.HandoffError(f"{name} is not on this machine's PATH")
  return found


def b64(data: bytes) -> str:
  return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def jwt(app_id: int, key, openssl: str, now=None) -> str:
  """The App's JWT: RS256, `iat` now - 60 s, `exp` now + 9 min, `iss` the app id; the key is read by
  openssl alone, the signature taken on stdin."""
  now = int(time.time()) if now is None else int(now)
  head = b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
  payload = b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}, separators=(",", ":")).encode("utf-8"))
  signed = subprocess.run([openssl, "dgst", "-sha256", "-sign", str(key)], input=f"{head}.{payload}".encode("ascii"),
                          capture_output=True)
  if signed.returncode:
    raise core.HandoffError(f"openssl dgst -sign failed: {signed.stderr.decode('utf-8', 'replace').strip()}")
  return f"{head}.{payload}.{b64(signed.stdout)}"


def api(method: str, path: str, auth: str, body: dict = None):
  """One request to the GitHub API as the JWT or the token `auth`, with a JSON `body` when given; an
  HTTP refusal or a transport error is a HandoffError naming the call."""
  request = Request(API + path, method=method, data=json.dumps(body).encode("utf-8") if body is not None else None,
                    headers={"Authorization": f"Bearer {auth}", "Accept": "application/vnd.github+json",
                             **({"Content-Type": "application/json"} if body is not None else {})})
  try:
    with urlopen(request, timeout=30) as response:
      return json.loads(response.read() or b"null")
  except HTTPError as error:
    body = error.read()
    try:
      message = json.loads(body).get("message") or body.decode("utf-8", "replace").strip()
    except ValueError:
      message = body.decode("utf-8", "replace").strip()
    raise core.HandoffError(f"{method} {path}: HTTP {error.code}: {message}") from None
  except URLError as error:
    raise core.HandoffError(f"{method} {path}: {error.reason}") from None


def mint(repo: str, app_id: int, key, openssl: str) -> str:
  """A one-hour installation token for `repo` alone: the installation that includes it, resolved on
  every mint (nothing is cached), then its access token scoped to the repository (`repositories`), so an
  installation that reaches other repositories still yields a token that reaches this one only."""
  token = jwt(app_id, key, openssl)
  installation = api("GET", f"/repos/{repo}/installation", token)
  return api("POST", f"/app/installations/{installation['id']}/access_tokens", token, {"repositories": [repo.split("/")[1]]})["token"]


FOUR = {"contents": "write", "issues": "write", "metadata": "read", "pull_requests": "write"}  # the installed permissions, exactly


def permission_set(permissions: dict) -> str:
  return "{" + ", ".join(f"{k}: {v}" for k, v in sorted(permissions.items())) + "}"


def app_lines(app: dict, repo: str, key, openssl: str) -> list:
  """`doctor`'s and `launch`'s App lines, in the order app, permissions, token, installation, each `ok…`
  or the refusal (a HandoffError's text is its line); the first that is not `ok` ends the list. By the
  owner's ruling of 2026-11-05 the App may be installed on several accounts: the installation that
  includes `repo` is the one `GET /repos/<repo>/installation` answers with, read for the permissions
  (never the repository's own) and on every mint, and the installation line reads only its repositories."""
  found, lines = {}, []

  def app_line():
    found["jwt"] = jwt(app["app_id"], key, openssl)
    data = api("GET", "/app", found["jwt"])
    if (data.get("slug"), data.get("id")) != (app["slug"], app["app_id"]):
      return f"GET /app answers {data.get('slug')} #{data.get('id')}, not builder.app ({app['slug']} #{app['app_id']})"
    return f"ok ({app['slug']} #{app['app_id']})"

  def permissions():
    installation = api("GET", f"/repos/{repo}/installation", found["jwt"])
    found["id"], installed = installation["id"], installation.get("permissions") or {}
    if installed != FOUR:
      return f"installed {permission_set(installed)}, not {permission_set(FOUR)}"
    return f"ok ({permission_set(installed)[1:-1]})"

  def token():
    found["token"] = api("POST", f"/app/installations/{found['id']}/access_tokens", found["jwt"], {"repositories": [repo.split("/")[1]]})["token"]
    return "ok"

  def installation():
    data = api("GET", "/installation/repositories", found["token"])
    if data.get("total_count") != 1:
      return f"the token reaches {data.get('total_count')} repositories, not {repo} alone"
    name = data["repositories"][0]["full_name"]
    return f"ok ({repo})" if name.lower() == repo.lower() else f"installed on {name}, not {repo}"

  for name, fn in (("app", app_line), ("permissions", permissions), ("token", token), ("installation", installation)):
    try:
      text = fn()
    except core.HandoffError as error:
      text = str(error)
    lines.append((name, text))
    if not text.startswith("ok"):
      break
  return lines
