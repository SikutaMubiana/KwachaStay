"""Create the GitHub repository for KwachaStay and push the current branch.

Requires GITHUB_TOKEN (fine-grained PAT with Administration: read/write and
Contents: read/write) and GITHUB_USERNAME in .env. The token is never printed.

Usage:
  python scripts/deploy_github.py --check   # verify configuration and repo state
  python scripts/deploy_github.py           # create the repo if needed and push
"""
import argparse
import base64
import json
import os
import subprocess
import urllib.error
import urllib.request

try:
    from postgres_schema import ROOT
except ImportError:  # imported as a package from the project root
    from scripts.postgres_schema import ROOT

API = 'https://api.github.com'
DEFAULT_REPO = 'kwachastay'


def load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / '.env')


def request(method, path, token, payload=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    request_headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if data is not None:
        request_headers['Content-Type'] = 'application/json'
    http_request = urllib.request.Request(
        f'{API}{path}', data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(http_request, timeout=30) as response:
            body = response.read()
            return response.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', 'replace')
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return error.code, body
    except urllib.error.URLError as error:
        raise SystemExit('The GitHub API could not be reached.') from error


def git(*args, check=True):
    return subprocess.run(
        ['git', *args], cwd=ROOT, check=check, capture_output=True, text=True
    )


def ensure_branch(name='main'):
    current = git('branch', '--show-current').stdout.strip()
    if current and current != name:
        git('branch', '-M', name)
        print(f'Renamed local branch "{current}" to "{name}".')
    return name


def push(token, owner, repo, branch):
    credentials = base64.b64encode(f'x-access-token:{token}'.encode('utf-8')).decode('ascii')
    header = f'AUTHORIZATION: basic {credentials}'
    git('remote', 'remove', 'origin', check=False)
    git('remote', 'add', 'origin', f'https://github.com/{owner}/{repo}.git')
    git('-c', f'http.extraheader={header}', 'push', '-u', 'origin', branch)
    print(f'Pushed branch "{branch}" to https://github.com/{owner}/{repo}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Only verify configuration')
    parser.add_argument('--repo', default=os.getenv('GITHUB_REPO', DEFAULT_REPO))
    parser.add_argument('--public', action='store_true', help='Create a public repository')
    args = parser.parse_args()

    load_env()
    token = os.getenv('GITHUB_TOKEN', '').strip()
    owner = os.getenv('GITHUB_USERNAME', '').strip()
    branch = ensure_branch('main')

    if args.check:
        print(f'GITHUB_USERNAME: {"SET" if owner else "EMPTY"}')
        print(f'GITHUB_TOKEN: {"SET" if token else "EMPTY"}')
        print(f'Repository: {owner or "<owner>"}/{args.repo}')
        print(f'Branch: {branch}')
        return

    if not token or not owner:
        raise SystemExit('Set GITHUB_TOKEN and GITHUB_USERNAME in .env first.')
    if git('status', '--porcelain').stdout.strip():
        raise SystemExit('Commit local changes before deploying to GitHub.')

    status, body = request('GET', f'/repos/{owner}/{args.repo}', token)
    if status == 200:
        print(f'Repository {owner}/{args.repo} already exists.')
    else:
        status, body = request(
            'POST', '/user/repos', token,
            {'name': args.repo, 'private': not args.public, 'auto_init': False},
        )
        if status != 201:
            raise SystemExit(f'Could not create repository (HTTP {status}): {body}')
        print(f'Created repository {owner}/{args.repo}.')

    push(token, owner, args.repo, branch)


if __name__ == '__main__':
    main()
