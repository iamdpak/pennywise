#!/bin/bash

NAME=${CONTAINER_NAME:-pennywise}

# Make sure there is a file here so that docker does't mount it as a folder
touch .docker_history
touch .env

## know what is interative and non interactive

docker run --user $(id -u) \
	--rm --tty --interactive \
	--network=host \
	--volume ${PWD}:${PWD} \
	--volume ${PWD}/.docker_history:/home/$(id --user --name)/.bash_history \
	--volume ${PWD}/.env:/home/$(id --user --name)/.env \
	--name ${NAME} \
	--hostname ${NAME} \
	--workdir ${PWD} \
	--env TERM=xterm-256color \
	--env XDG_RUNTIME_DIR=/run/user/1000 \
	--env DISPLAY \
	--gpus all \
	--volume /tmp/.x11-unix:/tmp/.X11-unix:rw \
	--ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
	--privileged -v /dev/bus/usb:/dev/bus/usb \
	--publish 5432:5432 \
	experiments/pennywise:latest \
	${1:-bash} \
	1>&2
