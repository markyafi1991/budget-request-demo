#!/usr/bin/env python3
"""Budget demo update review packets and hub PRs. Manual, no merge/release/export.

Version 1.0. Uses gh's existing credentials; never reads the vault or a token.
"""
from __future__ import annotations

import argparse
import base64
import copy
import difflib
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path, PurePosixPath

OWNER = "markyafi1991"
HUB = OWNER + "/budget-request-demo"
REPOS = [HUB, *(HUB + "-" + x for x in ("powerapps", "powerbi", "employees"))]
HEX = re.compile(r"^[0-9a-f]{40}$")
TOKEN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[abprs]-[\w-]{20,}|xapp-\d-[\w-]{20,}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}|sk-(?:ant-)?[A-Za-z0-9_-]{32,}|AKIA[A-Z0-9]{16}|AIza[\w-]{35}")
EXCLUDED = {"project-package.json", "CHANGELOG.md"}


class Error(Exception):
    pass


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict(data):
    def pairs(items):
        result = {}
        for key, val in items:
            if key in result:
                raise Error("Duplicate JSON key")
            result[key] = val
        return result
    return json.loads(data, object_pairs_hook=pairs)


def api(path, data=None, method=None):
    match = re.fullmatch(r"repos/([^/]+/[^/?]+)(/.*)?", path)
    if not match or match[1] not in REPOS:
        raise Error("Destination outside demo")
    if data is not None and (match[1] != HUB or match[2] not in
            {'/git/trees', '/git/commits', '/git/refs', '/pulls'} or method not in {None, 'POST'}):
        raise Error("Write outside approved hub proposal endpoints")
    if data is None and method is not None:
        raise Error("Read requests cannot specify a mutation method")
    args = ["gh", "api", "--hostname", "github.com", path]
    if data is not None:
        args += ["--method", method or "POST", "--input", "-"]
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        # Do not echo HTTP request bodies, credentials or untrusted server errors.
        raise Error("GitHub request failed; inspect destination and reconcile before retry")
    return strict(result.stdout) if result.stdout.strip() else None


def safe_path(path):
    p = PurePosixPath(path)
    parts = [unicodedata.normalize('NFC', x).casefold() for x in p.parts]
    forbidden = {".git", ".env", "10_personal", "12_wealth", "13_todoist", "14_bookmarks", "09_job_search", "02_clients", "tags", "private-data", "private-memory"}
    if (not path or p.is_absolute() or ".." in p.parts or "\\" in path
            or any(ord(x) < 32 or ord(x) == 127 or x == '`' for x in path)
            or any(x in forbidden or x.startswith(".env.") for x in parts)
            or any(x in {'.netrc', '.npmrc', 'credentials.json', 'token.json'} or x.startswith(('id_rsa', 'id_ed25519')) for x in parts)
            or p.suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}):
        raise Error("Unsafe/private file path")


def scan(path, data):
    safe_path(path)
    if len(data) > 1_000_000:
        raise Error("File exceeds reviewed text limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Error("Binary artifact needs a separately reviewed publication path") from exc
    if TOKEN.search(text):
        raise Error("Potential secret; no packet written")
    return text


def snapshot(repo, sha, gh=api):
    if repo not in REPOS or not HEX.fullmatch(sha):
        raise Error("Unapproved repository or revision")
    tree = gh(f"repos/{repo}/git/trees/{sha}?recursive=1")
    if tree.get("truncated") or len(tree["tree"]) > 500:
        raise Error("Incomplete or oversized inventory")
    result = {}
    total = 0
    for item in tree["tree"]:
        if item["type"] == "tree":
            continue
        if item["type"] != "blob" or item["mode"] != "100644" or item.get("size", 0) > 1_000_000:
            raise Error("Special, linked, executable or oversized artifact")
        safe_path(item["path"])
        if not HEX.fullmatch(item['sha']):
            raise Error("Invalid blob revision")
        blob = gh(f"repos/{repo}/git/blobs/{item['sha']}")
        data = base64.b64decode(blob["content"], validate=False)
        scan(item["path"], data)
        total += len(data)
        if total > 16_000_000:
            raise Error("Project snapshot exceeds reviewed limit")
        result[item["path"]] = data
    return result


def heads(gh=api):
    result = {}
    for repo in REPOS:
        meta = gh(f"repos/{repo}")
        if meta["full_name"] != repo or meta["private"] or meta.get("fork") or meta.get("archived"):
            raise Error("Destination identity/visibility changed")
        sha = gh(f"repos/{repo}/git/ref/heads/main")["object"]["sha"]
        if not HEX.fullmatch(sha):
            raise Error("Invalid branch revision")
        result[repo] = sha
    return result


def differences(repo, before, after):
    changes = []
    for path in sorted(set(before) | set(after)):
        if repo == HUB and (path in EXCLUDED or path.startswith("updates/")):
            continue
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        changes.append({"repository": repo, "path": path,
                        "change": "added" if old is None else "removed" if new is None else "modified",
                        "before_sha256": digest(old) if old is not None else None,
                        "after_sha256": digest(new) if new is not None else None,
                        "diff": "".join(difflib.unified_diff((old or b'').decode().splitlines(True),
                            (new or b'').decode().splitlines(True), fromfile="before/" + path, tofile="after/" + path))})
    return changes


def prepare(summary, why, actor, checks, version, upgrade, gh=api):
    for text in (summary, why, actor, upgrade):
        if (not text.strip() or len(text) > 4000 or TOKEN.search(text)
                or any(ord(x) < 32 or ord(x) == 127 for x in text)):
            raise Error("Missing, oversized or unsafe change notes")
    if len(summary) > 200:
        raise Error("PR summary exceeds reviewed title limit")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise Error("Use a three-part numeric version")
    if not isinstance(checks, list) or len(checks) > 100:
        raise Error("Checks must be an explicit list")
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {"check", "result", "evidence"}
                or check["result"] not in {"passed", "failed", "not-run"}
                or not all(isinstance(v, str) and len(v) <= 4000 and not any(ord(x) < 32 or ord(x) == 127 for x in v) for v in check.values())):
            raise Error("Malformed verification record")
    scan("checks.json", encoded(checks))
    current = heads(gh)
    hub = snapshot(HUB, current[HUB], gh)
    baseline = strict(hub["project-package.json"])
    if tuple(map(int, version.split('.'))) <= tuple(map(int, baseline['version'].split('.'))):
        raise Error("New package version must exceed the current version")
    if baseline.get('private_repository_dependencies'):
        raise Error("Public demo must not depend on private repositories")
    components = baseline["components"]
    if len(components) != 3 or {x["repository"] for x in components} != set(REPOS[1:]):
        raise Error("Component inventory differs from approved project")
    updated = copy.deepcopy(baseline)
    updated["version"] = version
    changes = []
    for component in updated["components"]:
        repo, old = component["repository"], component["commit"]
        before, after = snapshot(repo, old, gh), snapshot(repo, current[repo], gh)
        if component["sha256"] != {p: digest(v) for p, v in before.items()}:
            raise Error("Baseline component hashes do not match pinned source")
        compare = gh(f"repos/{repo}/compare/{old}...{current[repo]}")
        if compare["status"] not in {"ahead", "identical"}:
            raise Error("Component history was rewritten/diverged")
        changes += differences(repo, before, after)
        component.pop('readback_verified', None)
        component.update(commit=current[repo], files=len(after), sha256={p: digest(v) for p, v in after.items()}, source_hashes_checked_at_prepare=True)
    original_hub = baseline["hub_file_sha256"]
    latest_hub = {p: digest(v) for p, v in hub.items() if p not in EXCLUDED and not p.startswith("updates/")}
    for path in sorted(set(original_hub) | set(latest_hub)):
        safe_path(path)
        if original_hub.get(path) != latest_hub.get(path):
            changes.append({"repository": HUB, "path": path,
                "change": "added" if path not in original_hub else "removed" if path not in latest_hub else "modified",
                "before_sha256": original_hub.get(path), "after_sha256": latest_hub.get(path),
                "diff": f"Hub baseline stores hashes only. Current source: https://github.com/{HUB}/commit/{current[HUB]}"})
    updated["hub_file_sha256"] = latest_hub
    # Never turn reported checks into app/report/image/reproduction readiness.
    packet = {"schema": 1, "tool_sha256": digest(Path(__file__).read_bytes()),
              "heads": current, "summary": summary, "why": why, "actor": actor,
              "verification": checks, "verification_scope": "Owner/builder-reported evidence; updater did not execute app/report tests",
              "hub_inventory_sha256": {p: digest(v) for p, v in hub.items()},
              "upgrade": upgrade, "changes": changes, "previous_manifest": baseline,
              "next_manifest": updated, "previous_changelog": hub.get("CHANGELOG.md", b'').decode()}
    scan("packet.json", encoded(packet))
    if heads(gh) != current:
        raise Error("Repositories changed during preparation; retry read-only preparation")
    return packet


def inline(value):
    value = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('@', '＠')
    return re.sub(r'([\\`*_{}\[\]()#+.!|~])', r'\\\1', value)


def render(packet):
    lines = [f"## {packet['next_manifest']['version']} — {inline(packet['summary'])}", "",
             "Why: " + inline(packet['why']), "", "Actor/model: " + inline(packet['actor']), "",
             "### File changes", ""]
    lines += [f"- {x['change']}: {inline(x['repository'] + '/' + x['path'])}" for x in packet['changes']] or ["- No component/content changes; establishing or updating package metadata only."]
    lines += ["", "### Reported verification (not executed by updater)", ""]
    lines += [f"- {x['result']}: {inline(x['check'])} — {inline(x['evidence'])}" for x in packet['verification']] or ["- No verification supplied; app/report acceptance remains unverified."]
    lines += ["", "Upgrade: " + inline(packet['upgrade']), "", "Rollback: use the previous manifest's exact component commits; no history reset is performed. Commit retention is not guaranteed: retain complete release snapshots or owner-created tags.", "", "All hub file hashes, including metadata excluded from content-diff counts, are retained in the packet. Hub content is re-baselined by hash, not reconstructed historical text.", "", "This PR does not merge, publish a release, build/publish an image, export the private vault, or provision employee access.", ""]
    return "\n".join(lines)


def propose(raw, approved_sha256, gh=api):
    if digest(raw) != approved_sha256:
        raise Error("Review packet digest differs from approved packet")
    packet = strict(raw)
    if packet["tool_sha256"] != digest(Path(__file__).read_bytes()):
        raise Error("Updater changed since packet preparation")
    if set(packet["heads"]) != set(REPOS) or heads(gh) != packet["heads"]:
        raise Error("Repository changed after review; prepare a new packet")
    # Reconstruct reviewed bytes from the still-current public sources, not trusted packet fields.
    fresh = prepare(packet['summary'], packet['why'], packet['actor'], packet['verification'],
                    packet['next_manifest']['version'], packet['upgrade'], gh)
    if encoded(fresh) != raw:
        raise Error("Packet is not the exact canonical preparation")
    text = render(packet)
    branch = "codex/project-update-" + approved_sha256[:20]
    marker = "Project update packet " + approved_sha256
    base = packet['heads'][HUB]
    files = {"project-package.json": encoded(packet['next_manifest']).decode(),
             "CHANGELOG.md": "# Project Changelog\n\n" + text + "\n" + packet['previous_changelog'].removeprefix('# Project Changelog\n').lstrip('\n'),
             f"updates/{approved_sha256}.json": raw.decode()}
    tree = gh(f"repos/{HUB}/git/trees", {"base_tree": gh(f"repos/{HUB}/git/commits/{base}")['tree']['sha'],
             "tree": [{"path": p, "mode": "100644", "type": "blob", "content": v} for p, v in files.items()]})
    commit = gh(f"repos/{HUB}/git/commits", {"message": marker, "tree": tree['sha'], "parents": [base]})
    # Reconcile an uncertain ref creation. A conflicting or unrelated ref never gets overwritten.
    refs = gh(f"repos/{HUB}/git/matching-refs/heads/{branch}")
    exact = [x for x in refs if x['ref'] == 'refs/heads/' + branch]
    if exact:
        if not HEX.fullmatch(exact[0]['object']['sha']):
            raise Error("Invalid proposal revision")
        existing = gh(f"repos/{HUB}/git/commits/{exact[0]['object']['sha']}")
        if existing['message'] != marker or existing['tree']['sha'] != tree['sha'] or [p['sha'] for p in existing['parents']] != [base]:
            raise Error("Proposal branch differs from reviewed update")
    else:
        gh(f"repos/{HUB}/git/refs", {"ref": "refs/heads/" + branch, "sha": commit['sha']})
    prs = gh(f"repos/{HUB}/pulls?state=all&head={OWNER}:{branch}&base=main")
    if prs:
        if len(prs) != 1:
            raise Error("Prior proposal closed/changed; inspect instead of duplicating")
        verify_pr(prs[0], branch, base, tree['sha'], text, gh)
        return prs[0]['html_url']
    if heads(gh) != packet['heads']:
        raise Error("Repository changed before PR creation; proposal branch retained for inspection")
    gh(f"repos/{HUB}/pulls", {"title": packet['summary'], "head": branch,
                  "base": "main", "body": text, "draft": True})
    confirmed = gh(f"repos/{HUB}/pulls?state=all&head={OWNER}:{branch}&base=main")
    if len(confirmed) != 1:
        raise Error("PR result could not be verified; inspect before retrying")
    verify_pr(confirmed[0], branch, base, tree['sha'], text, gh)
    return confirmed[0]['html_url']


def verify_pr(pr, branch, base, tree, body, gh):
    if (pr.get('state') != 'open' or pr.get('draft') is not True or pr.get('body') != body
            or pr['head']['repo']['full_name'] != HUB or pr['base']['repo']['full_name'] != HUB
            or pr['head']['ref'] != branch or pr['base']['ref'] != 'main' or pr['base']['sha'] != base
            or not HEX.fullmatch(pr['head']['sha'])):
        raise Error("PR differs from reviewed proposal")
    commit = gh(f"repos/{HUB}/git/commits/{pr['head']['sha']}")
    if commit['tree']['sha'] != tree or [p['sha'] for p in commit['parents']] != [base]:
        raise Error("PR commit differs from reviewed tree/parent")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    for key in ('summary', 'why', 'actor', 'version', 'upgrade', 'checks', 'output'):
        p.add_argument('--' + key, required=True)
    p = sub.add_parser("propose")
    p.add_argument('--packet', required=True)
    p.add_argument('--approved-sha256', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            packet = prepare(args.summary, args.why, args.actor, strict(Path(args.checks).read_bytes()), args.version, args.upgrade)
            raw = encoded(packet)
            with Path(args.output).open('xb') as file:
                file.write(raw)
            print(f"Packet: {args.output}\nSHA-256: {digest(raw)}\nFiles changed: {len(packet['changes'])}")
        else:
            print(propose(Path(args.packet).read_bytes(), args.approved_sha256))
    except (Error, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"Stopped: {type(exc).__name__}: {exc}\n")


if __name__ == '__main__':
    main()
