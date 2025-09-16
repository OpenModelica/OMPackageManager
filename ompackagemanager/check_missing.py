from github import Github, Auth
import json
import os

def main():
    """Print all GitHub repositories missing from modelica-3rdparty.

    Check if GitHub user `modelica-3rdparty` has a repository or fork for
    each package of `repos.json`, that is hosted on GitHub.
    Prints the missing repositories.
    """

    token = Auth.Token(os.environ["GITHUB_AUTH"])
    github_api = Github(auth=token)
    data = json.load(open("repos.json"))
    namesInRepos = set()
    for entry in data.values():
        if "github" in entry:
            namesInRepos.add(entry["github"])

    for repo in list(github_api.get_user("modelica-3rdparty").get_repos()):
        if repo.full_name in namesInRepos:
            continue
        if repo.fork and repo.parent.full_name in namesInRepos:
            continue
        print(repo.full_name)
