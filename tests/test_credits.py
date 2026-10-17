import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from pac import credits
from pac.playlist import load

A = "4uLU6hMCjMI75M1A2tKUQC"
B = "11dFghVXANMlKmJXsNCbNl"
C = "7snQQk1zcKl8gZ92AnueZW"


def git(cwd, *args, name="Someone", email="someone@example.com"):
    env = dict(os.environ, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email,
               GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email)
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


class CreditsTest(unittest.TestCase):
    def test_login_from_email(self):
        self.assertEqual(credits.login_from_email("123+alice@users.noreply.github.com"), "alice")
        self.assertEqual(credits.login_from_email("bob@users.noreply.github.com"), "bob")
        self.assertIsNone(credits.login_from_email("carol@example.com"))

    def test_credits_authors_and_bot_co_authors(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            git(cwd, "init", "-q")
            (cwd / "playlists").mkdir()
            path = cwd / "playlists" / "mix.txt"
            path.write_text(f"# @playlist pl\nspotify:track:{A}\n")
            git(cwd, "add", ".")
            git(cwd, "commit", "-qm", "first", name="Alice", email="1+alice@users.noreply.github.com")

            path.write_text(path.read_text() + f"spotify:track:{B}\n")
            git(cwd, "commit", "-qam", "Add B\n\nCo-authored-by: bob <2+bob@users.noreply.github.com>",
                name="github-actions[bot]", email="41898282+github-actions[bot]@users.noreply.github.com")

            path.write_text(path.read_text() + f"spotify:track:{C}\n")
            git(cwd, "commit", "-qam", "Add C", name="Carol Smith", email="carol@example.com")

            old = os.getcwd()
            os.chdir(cwd)
            try:
                env = os.environ.pop("GITHUB_TOKEN", None)
                result = credits.song_credits(load(Path("playlists/mix.txt")))
            finally:
                os.chdir(old)
                if env is not None:
                    os.environ["GITHUB_TOKEN"] = env
        self.assertEqual(result, {A: "@alice", B: "@bob", C: "Carol Smith"})

    def test_outside_git_gives_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.txt"
            path.write_text(f"spotify:track:{A}\n")
            self.assertEqual(credits.blame(str(path)), {})


if __name__ == "__main__":
    unittest.main()
