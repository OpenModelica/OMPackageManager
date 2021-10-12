FROM openmodelica/openmodelica:v1.18.0-ompython

RUN pip3 install --no-cache-dir semantic_version PyGithub atlassian-python-api && pip3 install --no-cache-dir --only-binary :all: pygit2 && apt-get clean && rm -rf /tmp/* /var/tmp/*
