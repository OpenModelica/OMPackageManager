from github import Github
import json
import os
import pygit2


def main():
    """Print all GitHub repositories missing from modelica-3rdparty.

    Check if GitHub user `modelica-3rdparty` has a repository or fork for
    each package of `repos.json`, that is hosted on GitHub.
    Prints the missing repositories.
    """

    gh_auth = os.environ["GITHUB_AUTH"]
    g = Github(gh_auth)
    data = json.load(open("repos.json"))
    namesInRepos = set()
    for entry in data.values():
        if "github" in entry:
            namesInRepos.add(entry["github"])

    for repo in list(g.get_user("modelica-3rdparty").get_repos()):
        if repo.full_name in namesInRepos:
            continue
        if repo.fork and repo.parent.full_name in namesInRepos:
            continue
        print(repo.full_name)
