# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the App client (spec section 11).

"""superegm builder-token: a one-hour installation token of the builder App on stdout, minted over
`urllib` from an RS256 JWT `openssl` signs with the key file `builder.app.private_key_env` names;
read-only, no run card. `doctor` and `launch` read the App through the same client."""

import base64
import json
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import superegm as core

WRITES = frozenset()  # builder-token writes nothing
API = "https://api.github.com"


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


def api(method: str, path: str, auth: str):
  """One request to the GitHub API as the JWT or the token `auth`; an HTTP refusal or a transport
  error is a HandoffError naming the call."""
  request = Request(API + path, method=method,
                    headers={"Authorization": f"Bearer {auth}", "Accept": "application/vnd.github+json"})
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
  """A one-hour installation token for `repo`: the installation that includes it, resolved on every
  mint (nothing is cached), then its access token."""
  token = jwt(app_id, key, openssl)
  installation = api("GET", f"/repos/{repo}/installation", token)
  return api("POST", f"/app/installations/{installation['id']}/access_tokens", token)["token"]
