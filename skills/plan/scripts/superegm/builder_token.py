# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the App client (spec section 11).

"""superegm builder-token: a one-hour installation token of the builder App on stdout, minted over
`urllib` from an RS256 JWT `openssl` signs with the key file `builder.app.private_key_env` names;
read-only, no run card. `doctor` and `launch` read the App through the same client."""

import base64
import json
import subprocess
import time

import superegm as core

WRITES = frozenset()  # builder-token writes nothing


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
