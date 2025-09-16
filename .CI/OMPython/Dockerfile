FROM openmodelica/openmodelica:v1.25.1-ompython

RUN pip3 install --no-cache-dir \
  argparse \
  atlassian-python-api \
  PyGithub \
  semantic_version \
  && pip3 install --no-cache-dir --only-binary :all: pygit2 \
  && apt-get clean \
  && rm -rf /tmp/* /var/tmp/*
