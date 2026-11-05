# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U15's tests of the App client (spec section 11).

"""`superegm builder-token` and the App client: the RS256 JWT over a throwaway key, the mint and the
App lines over a faked `urllib`; never a real GitHub call, never a real key."""

import base64, io, json, re, shutil, subprocess, urllib.error
import pytest
from conftest import REPO, set_config
import superegm  # the harness reloads the package per test: read HandoffError at call time
from superegm import DEFAULT_CONFIG, builder_token
from superegm.builder_token import jwt

OPENSSL = shutil.which("openssl")
APP = {"app_id": 12345, "slug": "superegm-builder", "private_key_env": "SUPEREGM_APP_KEY"}
unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@pytest.fixture
def key(tmp_path):
  """A throwaway RSA key in a tmp dir: the JWT tests sign with it and never with the owner's."""
  if not OPENSSL:
    pytest.skip("openssl is not on PATH")
  path = tmp_path / "app.pem"
  subprocess.run([OPENSSL, "genrsa", "-out", str(path), "2048"], check=True, capture_output=True)
  return path


def test_jwt_is_rs256_over_the_app_id(key, tmp_path):
  head, payload, signature = jwt(12345, key, OPENSSL, now=1_700_000_000).split(".")
  assert json.loads(unb64(head)) == {"alg": "RS256", "typ": "JWT"} and json.loads(unb64(payload)) == {"iat": 1_699_999_940, "exp": 1_700_000_540, "iss": 12345}
  subprocess.run([OPENSSL, "rsa", "-in", key, "-pubout", "-out", tmp_path / "pub.pem"], check=True, capture_output=True)
  (tmp_path / "sig").write_bytes(unb64(signature))
  assert subprocess.run([OPENSSL, "dgst", "-sha256", "-verify", tmp_path / "pub.pem", "-signature", tmp_path / "sig"], input=f"{head}.{payload}".encode(), capture_output=True).stdout.strip() == b"Verified OK"
