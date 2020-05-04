FROM openmodelica/openmodelica:nightly-minimal-1.16-dev-20200430

RUN apt-get update && apt-get install -qyy python3 python3-pip libgit2-dev && pip3 install --no-cache-dir OMPython semantic_version pygit2 PyGithub && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
