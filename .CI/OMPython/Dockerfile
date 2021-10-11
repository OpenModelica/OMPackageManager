FROM openmodelica/openmodelica:nightly-minimal-1.16-dev-20200701

RUN apt install --reinstall ca-certificates && apt-get update && apt-get install -qyy python3 python3-pip libgit2-dev && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN pip3 install --no-cache-dir OMPython semantic_version PyGithub atlassian-python-api && pip3 install --no-cache-dir --only-binary :all: pygit2 && rm -rf /tmp/* /var/tmp/*
