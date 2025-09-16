import json
import semantic_version


def main():
    """Print used libraries for all packages in `index.json`."""
    data = json.load(open("index.json"))
    versionsWeHave = {}
    for lib in data["libs"].keys():
        versionsWeHave[lib] = set()
        versions = data["libs"][lib]["versions"]
        for version in versions.keys():
            versionsWeHave[lib].add(
                semantic_version.Version.coerce(version).truncate())
            for provide in versions[version].get("provides", []):
                versionsWeHave[lib].add(
                    semantic_version.Version.coerce(provide).truncate())
    print(versionsWeHave)
    for lib in data["libs"].keys():
        versions = data["libs"][lib]["versions"]
        for version in versions.keys():
            uses = versions[version].get("uses", {})
            for use in uses.keys():
                if use not in versionsWeHave:
                    print(
                        "%s %s uses unknown library %s %s" %
                        (lib, version, use, uses[use]))
                    continue
                if semantic_version.Version.coerce(
                        uses[use]).truncate() not in versionsWeHave[use]:
                    print("%s %s uses %s %s" % (lib, version, use, uses[use]))
                else:
                    pass  # print("Have %s %s" % (use, uses[use]))
