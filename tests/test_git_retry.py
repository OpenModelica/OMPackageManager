import os
import tempfile
import unittest
from unittest import mock

import pygit2

from ompackagemanager import updateinfo
from ompackagemanager.updateinfo import getgitrepo

GATEWAY_TIMEOUT = pygit2.GitError("unexpected http status code: 504")


def commit_file(repo, name):
    with open(os.path.join(repo.workdir, name), "w") as f:
        f.write(name)
    repo.index.add(name)
    repo.index.write()
    sig = pygit2.Signature("test", "test@example.com")
    parents = [] if repo.head_is_unborn else [repo.head.target]
    return str(repo.create_commit("HEAD", sig, sig, name, repo.index.write_tree(), parents))


class TestGitRetry(unittest.TestCase):
    """A git server that times out (gitlab.pam-retd.fr answering 504) must not stop the index update"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upstream = pygit2.init_repository(os.path.join(self.tmp.name, "upstream"))
        self.first = commit_file(self.upstream, "a.mo")
        self.url = self.upstream.path
        self.repopath = os.path.join(self.tmp.name, "cache", "Lib.git")
        getgitrepo(self.url, self.repopath)
        unfetched = mock.patch.object(updateinfo, "unfetchedRepos", [])
        unfetched.start()
        self.addCleanup(unfetched.stop)
        sleep = mock.patch.object(updateinfo.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def fetch_failing(self, times):
        real_fetch = pygit2.remotes.Remote.fetch
        calls = []

        def fetch(remote, *args, **kwargs):
            calls.append(1)
            if len(calls) <= times:
                raise GATEWAY_TIMEOUT
            return real_fetch(remote, *args, **kwargs)
        return mock.patch.object(pygit2.remotes.Remote, "fetch", fetch)

    def test_retry_then_fetch(self):
        second = commit_file(self.upstream, "b.mo")
        with self.fetch_failing(updateinfo.GIT_ATTEMPTS - 1):
            gitrepo = getgitrepo(self.url, self.repopath, second)
        self.assertIsNotNone(gitrepo.get(second))
        self.assertEqual(self.sleep.call_count, updateinfo.GIT_ATTEMPTS - 1)
        self.assertEqual(updateinfo.unfetchedRepos, [])

    def test_server_down_uses_cached_clone(self):
        commit_file(self.upstream, "b.mo")
        with self.fetch_failing(2 * updateinfo.GIT_ATTEMPTS):  # both calls below
            gitrepo = getgitrepo(self.url, self.repopath)
            self.assertIsNotNone(getgitrepo(self.url, self.repopath, self.first).get(self.first))
        self.assertIsNotNone(gitrepo.get(self.first))
        # reported in the summary at the end of the run, naming the repository
        self.assertEqual([url for url, error in updateinfo.unfetchedRepos], [self.url, self.url])
        self.assertIn("504", updateinfo.unfetchedRepos[0][1])

    def test_server_down_and_commit_not_cached(self):
        second = commit_file(self.upstream, "b.mo")
        with self.fetch_failing(updateinfo.GIT_ATTEMPTS):
            with self.assertRaises(pygit2.GitError) as raised:
                getgitrepo(self.url, self.repopath, second)
        # the error names the repository, not just the HTTP status
        self.assertIn(self.url, str(raised.exception))
        self.assertIn("504", str(raised.exception))
        self.assertIn(second, str(raised.exception))

    def test_failed_clone_is_retried_from_scratch(self):
        real_clone = pygit2.clone_repository
        calls = []

        def clone(url, path, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                os.makedirs(os.path.join(path, "half-done"))
                raise GATEWAY_TIMEOUT
            return real_clone(url, path, *args, **kwargs)
        repopath = os.path.join(self.tmp.name, "cache", "Other.git")
        with mock.patch.object(pygit2, "clone_repository", clone):
            gitrepo = getgitrepo(self.url, repopath)
        self.assertIsNotNone(gitrepo.get(self.first))
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
