ARG POSTGRES_TAG=latest

FROM postgres:${POSTGRES_TAG}

COPY . /
