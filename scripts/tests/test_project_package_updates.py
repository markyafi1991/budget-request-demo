import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

PATH = Path(__file__).resolve().parents[1] / 'project_packages' / 'update_project.py'
spec = importlib.util.spec_from_file_location('update_project', PATH)
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class GitHub:
    def __init__(self):
        self.heads = {r: str(i + 1) * 40 for i, r in enumerate(u.REPOS)}
        self.files = {(r, sha): {'README.md': b'Fictional demo\n'} for r, sha in self.heads.items()}
        self.baseline = {'version': '0.1.0', 'status': 'scaffold-not-release-ready',
                         'components': [{'repository': r, 'commit': self.heads[r], 'files': 1,
                                         'sha256': {'README.md': u.digest(b'Fictional demo\n')}} for r in u.REPOS[1:]],
                         'hub_file_sha256': {'README.md': u.digest(b'Fictional demo\n')},
                         'reproduction': {'app_built': False}, 'employee_image': {'digest': None}}
        self.files[(u.HUB, self.heads[u.HUB])]['project-package.json'] = u.encoded(self.baseline)
        self.writes = []
        self.blobs = {}
        self.refs = []
        self.prs = []
        self.new_tree = None
        self.diverged = False

    def __call__(self, path, data=None):
        repo = next(r for r in sorted(u.REPOS, key=len, reverse=True)
                    if path == 'repos/' + r or path.startswith('repos/' + r + '/'))
        suffix = path[len('repos/' + repo):]
        if data is not None:
            self.writes.append((repo, suffix, copy.deepcopy(data)))
            if suffix == '/git/trees':
                self.new_tree = data
                return {'sha': 'a' * 40}
            if suffix == '/git/commits':
                self.commit = {'message': data['message'], 'tree': {'sha': data['tree']},
                               'parents': [{'sha': x} for x in data['parents']]}
                return {'sha': 'b' * 40}
            if suffix == '/git/refs':
                self.refs = [{'ref': data['ref'], 'object': {'sha': data['sha']}}]
                return self.refs[0]
            if suffix == '/pulls':
                pr = {**data, 'state': 'open', 'html_url': 'https://github.com/example/pull/1',
                      'head': {'ref': data['head'], 'sha': 'b' * 40, 'repo': {'full_name': u.HUB}},
                      'base': {'ref': 'main', 'sha': self.heads[u.HUB], 'repo': {'full_name': u.HUB}}}
                self.prs.append(pr)
                return pr
            raise AssertionError('Unexpected write')
        if suffix == '':
            return {'full_name': repo, 'private': False, 'fork': False}
        if suffix == '/git/ref/heads/main':
            return {'object': {'sha': self.heads[repo]}}
        if suffix.startswith('/git/trees/'):
            sha = suffix.split('/')[3].split('?')[0]
            entries = []
            for name, body in self.files[(repo, sha)].items():
                blob = u.digest(body)[:40]
                self.blobs[blob] = body
                entries.append({'path': name, 'type': 'blob', 'mode': '100644', 'sha': blob, 'size': len(body)})
            return {'tree': entries, 'truncated': False}
        if suffix.startswith('/git/blobs/'):
            return {'content': base64.b64encode(self.blobs[suffix.split('/')[-1]]).decode()}
        if suffix.startswith('/compare/'):
            return {'status': 'diverged' if self.diverged else 'ahead'}
        if suffix.startswith('/git/commits/'):
            if suffix.endswith('b' * 40):
                return self.commit
            if suffix.endswith('d' * 40):
                return {'message': 'Human edit', 'tree': {'sha': 'd' * 40}, 'parents': [{'sha': self.heads[u.HUB]}]}
            return {'tree': {'sha': 'c' * 40}}
        if suffix.startswith('/git/matching-refs/'):
            return self.refs
        if suffix.startswith('/pulls?'):
            return self.prs
        raise AssertionError(path)


class Updates(unittest.TestCase):
    def prepare(self, gh, **kwargs):
        args = dict(summary='Establish update record', why='Make changes auditable', actor='Test builder',
                    checks=[{'check': 'App acceptance', 'result': 'not-run', 'evidence': 'App absent'}],
                    version='0.1.1', upgrade='No application upgrade; scaffold only', gh=gh)
        args.update(kwargs)
        return u.prepare(**args)

    def test_preparation_is_read_only_and_keeps_readiness_false(self):
        gh = GitHub()
        packet = self.prepare(gh)
        self.assertEqual(gh.writes, [])
        self.assertEqual(packet['changes'], [])
        self.assertFalse(packet['next_manifest']['reproduction']['app_built'])
        self.assertIsNone(packet['next_manifest']['employee_image']['digest'])
        self.assertIn('not-run', u.render(packet))

    def test_added_modified_removed_file_diff_and_hashes(self):
        gh = GitHub()
        repo = u.REPOS[1]
        old = gh.heads[repo]
        gh.files[(repo, old)]['remove.txt'] = b'old\n'
        gh.baseline['components'][0]['sha256']['remove.txt'] = u.digest(b'old\n')
        gh.files[(u.HUB, gh.heads[u.HUB])]['project-package.json'] = u.encoded(gh.baseline)
        gh.heads[repo] = 'e' * 40
        gh.files[(repo, gh.heads[repo])] = {'README.md': b'Changed\n', 'added.md': b'New\n'}
        packet = self.prepare(gh)
        self.assertEqual({x['change'] for x in packet['changes']}, {'added', 'modified', 'removed'})
        self.assertIn('-Fictional demo', packet['changes'][0]['diff'])
        self.assertEqual(packet['next_manifest']['components'][0]['commit'], 'e' * 40)

    def test_secret_stops_without_any_write(self):
        gh = GitHub()
        gh.files[(u.REPOS[1], gh.heads[u.REPOS[1]])]['oops.md'] = ('ghp_' + 'a' * 40).encode()
        with self.assertRaises(u.Error): self.prepare(gh)
        self.assertEqual(gh.writes, [])

    def test_private_paths_and_binary_refused(self):
        for name, body in [('10_Personal/note.md', b'no'), ('../README.md', b'no'),
                           ('.env', b'no'), ('bad.pbix', b'\xff')]:
            with self.subTest(name=name), self.assertRaises(u.Error): u.scan(name, body)

    def test_wrong_component_hash_or_history_refused(self):
        for diverged in (False, True):
            gh = GitHub()
            gh.diverged = diverged
            if not diverged:
                gh.files[(u.REPOS[1], gh.heads[u.REPOS[1]])]['README.md'] = b'tampered'
            with self.subTest(diverged=diverged), self.assertRaises(u.Error): self.prepare(gh)
            self.assertEqual(gh.writes, [])

    def test_forged_packet_and_changed_heads_cannot_write(self):
        gh = GitHub()
        packet = self.prepare(gh)
        packet['next_manifest']['reproduction']['app_built'] = True
        raw = u.encoded(packet)
        with self.assertRaises(u.Error): u.propose(raw, u.digest(raw), gh)
        self.assertEqual(gh.writes, [])
        packet = self.prepare(gh)
        raw = u.encoded(packet)
        gh.heads[u.REPOS[1]] = 'e' * 40
        with self.assertRaises(u.Error): u.propose(raw, u.digest(raw), gh)
        self.assertEqual(gh.writes, [])

    def test_proposal_only_writes_hub_draft_branch_and_is_retry_safe(self):
        gh = GitHub()
        raw = u.encoded(self.prepare(gh))
        one = u.propose(raw, u.digest(raw), gh)
        two = u.propose(raw, u.digest(raw), gh)
        self.assertEqual(one, two)
        self.assertEqual(len(gh.prs), 1)
        self.assertTrue(gh.prs[0]['draft'])
        self.assertTrue(all(repo == u.HUB for repo, _, _ in gh.writes))
        self.assertTrue(all(path not in {'/releases', '/merges'} for _, path, _ in gh.writes))
        self.assertTrue(gh.refs[0]['ref'].startswith('refs/heads/codex/'))
        self.assertEqual(gh.heads[u.HUB], '1' * 40)

    def test_changed_existing_proposal_is_not_overwritten(self):
        gh = GitHub()
        raw = u.encoded(self.prepare(gh))
        u.propose(raw, u.digest(raw), gh)
        gh.prs[0]['body'] = 'Human changed this'
        with self.assertRaises(u.Error): u.propose(raw, u.digest(raw), gh)
        self.assertEqual(gh.prs[0]['body'], 'Human changed this')

    def test_version_must_advance(self):
        for version in ('0.1.0', '0.0.9'):
            gh = GitHub()
            with self.subTest(version=version), self.assertRaises(u.Error): self.prepare(gh, version=version)
            self.assertEqual(gh.writes, [])

    def test_duplicate_json_and_wrong_approval_digest(self):
        with self.assertRaises(u.Error): u.strict('{"a": 1, "a": 2}')
        gh = GitHub()
        raw = u.encoded(self.prepare(gh))
        with self.assertRaises(u.Error): u.propose(raw, '0' * 64, gh)
        self.assertEqual(gh.writes, [])

    def test_repo_changes_during_preparation(self):
        gh = GitHub()
        count = 0
        def moving(path, data=None):
            nonlocal count
            if path.endswith('/git/ref/heads/main'):
                count += 1
                if count == 5: gh.heads[u.HUB] = 'e' * 40
            return gh(path, data)
        with self.assertRaises(u.Error): self.prepare(moving)
        self.assertEqual(gh.writes, [])

    def test_truncated_and_symlink_inventory_refused(self):
        for bad in ({'tree': [], 'truncated': True},
                    {'tree': [{'path': 'link.md', 'mode': '120000', 'type': 'blob'}]}):
            with self.subTest(bad=bad), self.assertRaises(u.Error):
                u.snapshot(u.HUB, 'a' * 40, lambda *args: bad)

    def test_private_destination_refused(self):
        gh = GitHub()
        def private(path, data=None):
            result = gh(path, data)
            if path == 'repos/' + u.REPOS[1]: result['private'] = True
            return result
        with self.assertRaises(u.Error): self.prepare(private)
        self.assertEqual(gh.writes, [])

    def test_api_host_and_write_boundary(self):
        with patch.object(u.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')) as run:
            u.api('repos/' + u.HUB)
            self.assertEqual(run.call_args.args[0][2:4], ['--hostname', 'github.com'])
            for path in ('repos/' + u.HUB + '-other/git/refs',
                         'repos/' + u.REPOS[1] + '/git/refs',
                         'repos/' + u.HUB + '/releases', 'repos/other/budget-request-demo/git/refs'):
                with self.subTest(path=path), self.assertRaises(u.Error): u.api(path, {})
            self.assertEqual(run.call_count, 1)

    def test_api_failure_does_not_echo_server_error(self):
        with patch.object(u.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'SECRET_SERVER_BODY')):
            with self.assertRaisesRegex(u.Error, 'GitHub request failed') as caught: u.api('repos/' + u.HUB)
            self.assertNotIn('SECRET_SERVER_BODY', str(caught.exception))

    def test_changelog_does_not_repeat_header(self):
        gh = GitHub()
        gh.files[(u.HUB, gh.heads[u.HUB])]['CHANGELOG.md'] = b'# Project Changelog\n\n## 0.1.0\n\nPrior owner entry\n'
        raw = u.encoded(self.prepare(gh))
        u.propose(raw, u.digest(raw), gh)
        body = next(x['content'] for x in gh.new_tree['tree'] if x['path'] == 'CHANGELOG.md')
        self.assertEqual(body.count('# Project Changelog'), 1)
        self.assertIn('Prior owner entry', body)

    def test_interrupted_before_pr_creation_can_resume(self):
        gh = GitHub()
        raw = u.encoded(self.prepare(gh))
        def fail_once(path, data=None):
            if path.endswith('/pulls') and data: raise u.Error('Simulated timeout')
            return gh(path, data)
        with self.assertRaisesRegex(u.Error, 'Simulated timeout'): u.propose(raw, u.digest(raw), fail_once)
        self.assertEqual(len(gh.refs), 1)
        self.assertEqual(len(gh.prs), 0)
        u.propose(raw, u.digest(raw), gh)
        self.assertEqual(len(gh.refs), 1)
        self.assertEqual(len(gh.prs), 1)

    def test_conflicting_branch_and_closed_or_wrong_head_pr_refused(self):
        for defect in ('tree', 'closed', 'head'):
            gh = GitHub()
            raw = u.encoded(self.prepare(gh))
            u.propose(raw, u.digest(raw), gh)
            if defect == 'closed': gh.prs[0]['state'] = 'closed'
            if defect == 'head': gh.prs[0]['head']['sha'] = 'd' * 40
            if defect == 'tree':
                # Change what the already-existing branch points to without changing new commit creation.
                gh.refs[0]['object']['sha'] = 'd' * 40
            with self.subTest(defect=defect), self.assertRaises(u.Error): u.propose(raw, u.digest(raw), gh)
            self.assertEqual(len(gh.prs), 1)

    def test_exact_proposal_file_inventory_and_write_endpoints(self):
        gh = GitHub()
        raw = u.encoded(self.prepare(gh))
        u.propose(raw, u.digest(raw), gh)
        self.assertEqual([path for _, path, _ in gh.writes], ['/git/trees', '/git/commits', '/git/refs', '/pulls'])
        self.assertEqual({x['path'] for x in gh.new_tree['tree']}, {'project-package.json', 'CHANGELOG.md', 'updates/' + u.digest(raw) + '.json'})

    def test_metadata_inventory_is_present_and_sources_not_called_published(self):
        gh = GitHub()
        gh.files[(u.HUB, gh.heads[u.HUB])]['updates/owner.json'] = b'{}'
        packet = self.prepare(gh)
        self.assertIn('updates/owner.json', packet['hub_inventory_sha256'])
        for item in packet['next_manifest']['components']:
            self.assertNotIn('readback_verified', item)
            self.assertTrue(item['source_hashes_checked_at_prepare'])

    def test_control_characters_and_mentions_cannot_forge_changelog(self):
        gh = GitHub()
        with self.assertRaises(u.Error): self.prepare(gh, summary='Update\n## Fake approval')
        with self.assertRaises(u.Error): u.safe_path('file`\nname.md')
        packet = self.prepare(gh, summary='@someone [Click](https://bad.invalid)')
        body = u.render(packet)
        self.assertNotIn('@someone', body)
        self.assertIn('\\[Click\\]', body)


if __name__ == '__main__':
    unittest.main()
