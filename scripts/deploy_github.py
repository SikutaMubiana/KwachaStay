"""Safely push KwachaStay to GitHub."""
import argparse
import base64
import json
import os
import subprocess
import urllib.error
import urllib.request

try:
    from postgres_schema import ROOT
except ImportError:
    from scripts.postgres_schema import ROOT

API = "https://api.github.com"
DEFAULT_REPO = "KwachaStay"


def load_env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")


def request(method, path, token, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{API}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return response.status, json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return error.code, body
    except urllib.error.URLError:
        raise SystemExit("Could not connect to the GitHub API.")


def git(*args, env=None, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def ensure_branch(name="main"):
    current = git("branch", "--show-current").stdout.strip()
    if current and current != name:
        git("branch", "-M", name)
        print(f"Renamed branch to {name}.")
    return name


def push(token, owner, repo, branch):
    credentials = base64.b64encode(
        f"x-access-token:{token}".encode("utf-8")
    ).decode("ascii")

    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraheader"
    env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {credentials}"

    git("remote", "remove", "origin", check=False)
    git("remote", "add", "origin", f"https://github.com/{owner}/{repo}.git")

    result = git("push", "-u", "origin", branch, env=env, check=False)

    if result.returncode != 0:
        raise SystemExit(
            "GitHub push failed. Check your token permissions and repository access.\n"
            + result.stderr.replace(credentials, "[REDACTED]")
        )

    print(f"Successfully pushed {branch} to GitHub.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()

    load_env()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    owner = os.getenv("GITHUB_USERNAME", "").strip()
    branch = ensure_branch("main")

    if args.check:
        print(f"GITHUB_USERNAME: {'SET' if owner else 'EMPTY'}")
        print(f"GITHUB_TOKEN: {'SET' if token else 'EMPTY'}")
        print(f"Repository: {owner or '<owner>'}/{args.repo}")
        print(f"Branch: {branch}")
        return

    if not token or not owner:
        raise SystemExit("Set GITHUB_TOKEN and GITHUB_USERNAME in .env.")

    if git("status", "--porcelain").stdout.strip():
        raise SystemExit("Commit local changes before deploying.")

    status, body = request("GET", f"/repos/{owner}/{args.repo}", token)

    if status != 200:
        raise SystemExit(
            f"Could not access repository (HTTP {status}). "
            "Check repository name and token permissions."
        )

    print(f"Repository {owner}/{args.repo} exists.")
    push(token, owner, args.repo, branch)


if __name__ == "__main__":
    main()