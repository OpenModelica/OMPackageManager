import os
import semantic_version


def write_problems(path: str, title: str, problems: list[str]) -> None:
    """Write what a command skipped to path, for Jenkins to mark the job unstable and mail it.

    The file is removed when nothing was skipped, so a stale one never outlives a clean run.
    """
    if not problems:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "w") as f:
        f.write("%s\n\n" % title)
        for problem in problems:
            f.write("- %s\n" % problem)


def VersionNumber(s: str) -> semantic_version.Version:
    if s.startswith("v"):
        s = s[1:]
    if s == "":
        return semantic_version.Version(major=0, minor=0, patch=0)
    try:
        return semantic_version.Version.coerce(s)
    except BaseException:
        return semantic_version.Version(major=0, minor=0, patch=0, prerelease=(s,))


def findMatchingLevel(s: str, levels: list[str]) -> str | None:
    try:
        vn = VersionNumber(s)
    except BaseException:
        return None
    for level in levels:
        if level[0].startswith("+") and len(vn.build) > 0 and level[0][1:] == ".".join(vn.build):
            return level[1]
        if level[0] == "prerelease" and len(vn.prerelease) > 0:
            return level[1]
        elif level[0] == "*":
            return level[1]
        elif level[0].startswith(">=") and vn >= VersionNumber(level[0][2:]):
            return level[1]
        elif level[0] == s:
            return level[1]
    return None


def getSupportLevel(tagName: str, levels: list[str]) -> str:
    res = findMatchingLevel(tagName, levels)
    if res is None:
        return "noSupport"
    if res not in [
        "fullSupport",
        "support",
        "experimental",
        "obsolete",
        "unknown",
            "noSupport"]:
        return "noSupport"
    return res
