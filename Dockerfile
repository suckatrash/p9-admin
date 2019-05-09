
# Python support can be specified down to the minor or micro version
# (e.g. 3.6 or 3.6.3).
# OS Support also exists for jessie & stretch (slim and full).
# See https://hub.docker.com/r/library/python/ for all supported Python
# tags from Docker Hub.
FROM python:alpine

LABEL Name=p9-admin Version=0.9.3

WORKDIR /app
ADD . /app

RUN apk update && \
    apk upgrade && \
    apk add --no-cache g++ gcc libc-dev libffi-dev linux-headers openldap-dev yaml-dev && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools wheel twine

RUN python3 setup.py build
RUN python3 setup.py install

ENTRYPOINT ["/usr/local/bin/p9-admin"]
