FROM ubuntu:resolute

# omc from OpenModelica's nightly packages, whose getExternalFunctions describes
# the prebuilt wasm modules; clang/lld/llvm compile them; python3 is 3.14, the
# build Python the CPython cross-build needs
RUN export DEBIAN_FRONTEND=noninteractive \
  && apt-get update \
  && apt-get install -qy --no-install-recommends ca-certificates curl gpg \
  && curl -fsSL https://build.openmodelica.org/apt/openmodelica.asc \
    | gpg --dearmor -o /usr/share/keyrings/openmodelica-keyring.gpg \
  && echo "deb [signed-by=/usr/share/keyrings/openmodelica-keyring.gpg] https://build.openmodelica.org/apt resolute nightly" \
    > /etc/apt/sources.list.d/openmodelica.list \
  && apt-get update \
  && apt-get install -qy --no-install-recommends \
    omc cmake git make \
    clang lld llvm libclang-rt-dev-wasm32 \
    python3 python3-pip python3-github python3-psutil python3-pygit2 python3-requests \
    python3-semantic-version python3-zmq \
  && pip3 install --no-cache-dir --break-system-packages atlassian-python-api OMPython==4.0.0 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
