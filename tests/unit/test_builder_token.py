# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U15's tests of the App client (spec section 11).

"""`superegm builder-token` and the App client: the RS256 JWT over a throwaway key, the mint and the
App lines over a faked `urllib`; never a real GitHub call, never a real key."""

import base64, io, json, re, shutil, subprocess, urllib.error
import pytest
from conftest import REPO, set_config
import superegm  # the harness reloads the package per test: read HandoffError at call time
from superegm import DEFAULT_CONFIG, builder_token
from superegm.builder_token import jwt, mint, app_lines

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


PERMISSIONS = {"contents": "write", "pull_requests": "write", "issues": "write", "metadata": "read"}
ROUTES = {("GET", "/app"): {"id": 12345, "slug": "superegm-builder"}, ("GET", f"/repos/{REPO}/installation"): {"id": 777, "permissions": PERMISSIONS},
          ("POST", "/app/installations/777/access_tokens"): {"token": "ghs_minted"}, ("GET", "/installation/repositories"): {"total_count": 1, "repositories": [{"full_name": REPO}]}}


def app_api(monkeypatch, answers=None) -> list:
  """`builder_token.urlopen` replaced by a function answering `ROUTES` then `answers` by `(method, path)` with
  `io.BytesIO` of the JSON, or raising `urllib.error.HTTPError` with the body `{"message": …}` for a
  `(status, message)` value; returns the `(method, path, authorization)` calls made."""
  routes, calls = {**ROUTES, **(answers or {})}, []

  def urlopen(request, timeout=None):
    method, path = request.get_method(), request.full_url.removeprefix("https://api.github.com")
    calls.append((method, path, request.get_header("Authorization"), json.loads(request.data) if request.data else None))
    answer = routes.get((method, path), (404, "Not Found"))
    if isinstance(answer, tuple):
      raise urllib.error.HTTPError(request.full_url, answer[0], answer[1], {}, io.BytesIO(json.dumps({"message": answer[1]}).encode("utf-8")))
    return io.BytesIO(json.dumps(answer).encode("utf-8"))

  monkeypatch.setattr(builder_token, "urlopen", urlopen)
  return calls


def test_mint_walks_two_calls_over_urllib_and_reports_the_refusal_verbatim(key, monkeypatch):
  calls = app_api(monkeypatch)
  assert mint(REPO, 12345, key, OPENSSL) == "ghs_minted"
  assert [c[:2] for c in calls] == [("GET", f"/repos/{REPO}/installation"), ("POST", "/app/installations/777/access_tokens")]
  assert calls[1][3] == {"repositories": [REPO.split("/")[1]]}, "the token is scoped to the repository alone (2026-11-06: an installation may reach several)"
  app_api(monkeypatch, {("POST", "/app/installations/777/access_tokens"): (403, "You have exceeded a secondary rate limit")})
  with pytest.raises(superegm.HandoffError, match=re.escape("POST /app/installations/777/access_tokens: HTTP 403: You have exceeded a secondary rate limit")):
    mint(REPO, 12345, key, OPENSSL)


def test_builder_token_prints_the_token_or_the_refusal(world, monkeypatch, key):
  app_api(monkeypatch)
  monkeypatch.setenv("SUPEREGM_APP_KEY", str(key))
  assert world.run("builder-token", "--repo", REPO, "--app-id", 12345, "--key-env", "SUPEREGM_APP_KEY", "--openssl", OPENSSL) == (0, "ghs_minted\n")
  set_config(world, repo=REPO, builder={**DEFAULT_CONFIG["builder"], "app": APP})
  assert world.run("builder-token") == (0, "ghs_minted\n") and world.gh.calls == []
  monkeypatch.delenv("SUPEREGM_APP_KEY")
  assert world.run("builder-token") == (1, "superegm: builder-token: SUPEREGM_APP_KEY is not set\n")


FOUR = "{contents: write, issues: write, metadata: read, pull_requests: write}"
OK = [("app", "ok (superegm-builder #12345)"), ("permissions", f"ok ({FOUR[1:-1]})"), ("token", "ok"), ("installation", f"ok ({REPO})")]


@pytest.mark.parametrize("answers, lines", [
  ({}, OK),
  ({("GET", f"/repos/{REPO}/installation"): {"id": 777, "permissions": {**PERMISSIONS, "administration": "write"}}},
   OK[:1] + [("permissions", f"installed {{administration: write, contents: write, issues: write, metadata: read, pull_requests: write}}, not {FOUR}")]),
  ({("GET", f"/repos/{REPO}/installation"): (404, "Not Found")}, OK[:1] + [("permissions", f"GET /repos/{REPO}/installation: HTTP 404: Not Found")]),
])
def test_app_lines_read_the_installation(key, monkeypatch, answers, lines):
  calls = app_api(monkeypatch, {("GET", f"/repos/{REPO}"): {"permissions": {"push": False}}, ("GET", "/app/installations"): [{"id": 777}, {"id": 778}], **answers})
  assert app_lines(APP, REPO, key, OPENSSL) == lines and not {("GET", f"/repos/{REPO}"), ("GET", "/app/installations")} & {c[:2] for c in calls}
