#!/bin/bash

NAME=${CONTAINER_NAME:-postgresdb}

# Make sure there is a file here so that docker does't mount it as a folder
touch .docker_history
touch .env

mkdir -p ${PWD}/data/postgresdb
sudo chown -R 999:999 ${PWD}/data/postgresdb
sudo chmod 700 ${PWD}/data/postgresdb


## know what is interative and non interactive

docker run --user postgres \
	--rm --tty --interactive \
	--network=docker_ragflow \
	--volume ${PWD}/data/postgresdb:/var/lib/postgresql/data \
	--name ${NAME} \
	--hostname ${NAME} \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=password \
    -e POSTGRES_DB=postgres \
	--env TERM=xterm-256color \
	--publish 5433:5432 \
	experiments/postgres:latest
	
