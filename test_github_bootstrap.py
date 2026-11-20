"""Directed, zero-network gate for a sovereign's GitHub onboarding proposal."""
import copy
import json
import unittest
from unittest import mock

import github_bootstrap as G


def repo(name="lab", *, private=False, fork=False, archived=False):
    return {
        "name": name, "full_name": f"owner-1/{name}",
        "html_url": f"https://github.com/owner-1/{name}",
        "private": private, "fork": fork, "archived": archived,
        "default_branch": "main",
    }


def snapshot(*rows):
    return {
        "schema": G.IN_SCHEMA,
        "source": "github.com",
        "owner": "owner-1",
        "repositories": list(rows),
    }


class GitHubBootstrapCases(unittest.TestCase):
    def assertRefused(self, value, cause):
        got = G.propose(value)
        self.assertEqual(got, {"schema": G.OUT_SCHEMA, "state": "NO_DATA",
                               "cause": cause, "changed": False})

    def test_valid_public_proposal_has_no_live_or_model_claim(self):
        s = snapshot(repo("lab"), repo("preceptoros-companion", fork=True),
                     repo("project-one", archived=True))
        result = G.propose(s)
        self.assertEqual(result["state"], "PROPOSED")
        self.assertFalse(result["changed"])
        self.assertEqual(result["capabilities"]["lab_source"], "DECLARED")
        self.assertEqual(result["capabilities"]["companion_source"], "DECLARED")
        self.assertEqual(result["capabilities"]["live_node"]["state"], "NO_DATA")
        self.assertEqual(result["capabilities"]["local_model"]["state"], "NO_DATA")
        self.assertEqual(result["capabilities"]["active_automations"]["state"], "NO_DATA")
        self.assertEqual(len(result["next_steps"]), 6)
        self.assertEqual(result["public_repositories"][1]["source_type"], "FORK")

    def test_private_repo_does_not_leak_name_or_url(self):
        s = snapshot(repo("SECRET_PERSONAL", private=True), repo("lab"))
        result = G.propose(s)
        self.assertEqual(result["private_repositories"]["count_only"], 1)
        self.assertEqual(len(result["public_repositories"]), 1)
        self.assertNotIn("SECRET_PERSONAL", json.dumps(result))
        self.assertEqual(result["capabilities"]["github_private_access"]["state"], "NO_DATA")

    def test_no_repo_is_not_no_consent(self):
        result = G.propose(snapshot())
        self.assertEqual(result["state"], "PROPOSED")
        self.assertEqual(result["public_repositories"], [])
        self.assertEqual(result["capabilities"]["lab_source"], "NO_DATA")

    def test_valid_sha_is_only_declared(self):
        row = repo()
        row["head_sha"] = "a" * 40
        self.assertEqual(G.propose(snapshot(row))["public_repositories"][0]["head"],
                         {"state": "OWNER_SUPPLIED_UNVERIFIED", "sha": "a" * 40})

    def test_no_sha_is_explained(self):
        result = G.propose(snapshot(repo()))
        self.assertEqual(result["public_repositories"][0]["head"]["cause"],
                         "head_revision_not_supplied")

    def test_duplicate_names_even_private_and_public_are_refused(self):
        self.assertRefused(snapshot(repo("LAB"), repo("lab", private=True)),
                           "repository_duplicate")

    def test_snapshot_extra_field_cannot_inject_authority(self):
        s = snapshot(repo())
        s["grant"] = "ALL"
        self.assertRefused(s, "snapshot_shape_invalid")

    def test_repository_extra_field_cannot_inject_command(self):
        row = repo()
        row["execute"] = "curl secret"
        self.assertRefused(snapshot(row), "repository_shape_invalid")

    def test_remote_url_is_exact_github_host_and_path(self):
        for url in ["http://github.com/owner-1/lab",
                    "https://github.com.evil.example/owner-1/lab",
                    "https://github.com/owner-1/lab?token=secret",
                    "https://github.com/owner-1/lab#fragment",
                    "https://user:pass@github.com/owner-1/lab",
                    "https://github.com/owner-1/other",
                    "file:///private/data"]:
            with self.subTest(url=url):
                row = repo()
                row["html_url"] = url
                self.assertRefused(snapshot(row), "repository_url_invalid")

    def test_owner_must_match_every_repo(self):
        s = snapshot(repo())
        s["owner"] = "other"
        self.assertRefused(s, "repository_identity_invalid")

    def test_unsafe_owner_name_is_refused(self):
        for name in ["../owner", "a--b", "bad name", "a" * 40, "-a", "a-"]:
            with self.subTest(name=name):
                s = snapshot()
                s["owner"] = name
                self.assertRefused(s, "owner_login_invalid")

    def test_unsafe_repo_name_is_refused(self):
        for name in ["..", ".git", ".hidden", "bad name", "a" * 101]:
            with self.subTest(name=name):
                row = repo()
                row["name"] = name
                row["full_name"] = "owner-1/" + name
                row["html_url"] = "https://github.com/owner-1/" + name
                self.assertRefused(snapshot(row), "repository_identity_invalid")

    def test_branch_scope_is_validated(self):
        for branch in ["../main", "refs/../private", "main name", "", "a" * 128]:
            with self.subTest(branch=branch):
                row = repo()
                row["default_branch"] = branch
                self.assertRefused(snapshot(row), "repository_branch_invalid")

    def test_nonboolean_flags_cannot_authorize_private_data(self):
        row = repo()
        row["private"] = "false"
        self.assertRefused(snapshot(row), "repository_flags_invalid")

    def test_bad_sha_is_rejected(self):
        row = repo()
        row["head_sha"] = "x" * 40
        self.assertRefused(snapshot(row), "repository_revision_invalid")

    def test_repository_limit_is_hard(self):
        self.assertRefused(snapshot(*(repo(f"r{i}") for i in range(101))),
                           "repository_limit")

    def test_byte_limit_is_hard(self):
        many = snapshot(*(repo(f"repo-{i}-{'a'*60}") for i in range(100)))
        # Add allowable optional SHAs to cross the 64-KiB cap if needed.
        for row in many["repositories"]:
            row["head_sha"] = "a" * 40
        got = G.propose(many)
        self.assertIn(got["state"], {"NO_DATA", "PROPOSED"})
        huge = snapshot()
        huge["repositories"] = [repo("lab")] * 100
        huge["source"] = "github.com" + "X" * G.MAX_INPUT_BYTES
        self.assertRefused(huge, "snapshot_byte_limit")

    def test_integrity_digest_is_deterministic_and_not_a_signature(self):
        s = snapshot(repo("lab"))
        original = copy.deepcopy(s)
        first = G.propose(s)
        second = G.propose(copy.deepcopy(s))
        self.assertEqual(first, second)
        self.assertEqual(s, original)
        self.assertEqual(len(first["source_integrity_sha256"]), 64)
        self.assertEqual(first["owner_authentication"]["cause"],
                         "github_owner_identity_not_authenticated")

    def test_never_network_or_processes(self):
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            with mock.patch("subprocess.run", side_effect=AssertionError("command")):
                out = G.propose(snapshot(repo()))
        self.assertFalse(out["changed"])
        self.assertEqual(out["state"], "PROPOSED")

    def test_invalid_structures_do_not_raise(self):
        for value in [None, [], "", {"repositories": []},
                      {**snapshot(), "repositories": "not-list"},
                      {**snapshot(), "repositories": [{}]},
                      {**snapshot(), "source": "github.evil"}]:
            with self.subTest(value=str(value)[:50]):
                self.assertEqual(G.propose(value)["state"], "NO_DATA")

    def test_role_hints_do_not_imply_provisioning(self):
        result = G.propose(snapshot(repo("preceptoros-web"), repo("preceptoros-app")))
        roles = {r["purpose_hint"] for r in result["public_repositories"]}
        self.assertEqual(roles, {"APP_SOURCE", "PUBLIC_WINDOW_SOURCE"})
        self.assertEqual(result["capabilities"]["live_node"]["state"], "NO_DATA")


if __name__ == "__main__":
    unittest.main()
