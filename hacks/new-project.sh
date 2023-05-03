#!/bin/bash

usage() { echo "Usage: ${0} <projectname> [stages, comma separated]" 1>&2; exit 1; }

while getopts "h" o; do
    case "${o}" in
        h)
            usage
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))


if [ $# -lt 1 ]; then
  usage
fi

if [ $# -gt 2 ]; then
  usage
fi

PROJECT="${1}"
STAGES=$(echo -n "${2:-"int,prod"}" | tr ',' ' ')
VALUESDIR="projects/${PROJECT}/values"
LINKDIR=".project-values"
mkdir -p "projects/${PROJECT}/applications"
mkdir -p "${VALUESDIR}/clusters"
mkdir -p "${VALUESDIR}/groups"
if ! [ -e "projects/${PROJECT}/README.md" ]; then
  echo -e "# Project: ${PROJECT}\n\nFact sheet: [${PROJECT}](https://...)" > "projects/${PROJECT}/README.md"
fi

# git does not store empty directories so create placeholder files
touch "projects/${PROJECT}/applications/.gitkeep"
touch "${VALUESDIR}/clusters/.gitkeep"
touch "${VALUESDIR}/groups/.gitkeep"

for stage in ${STAGES}
do
  mkdir -p "instances/${stage}/${LINKDIR}/"
  ln -s "../../../${VALUESDIR}" "instances/${stage}/${LINKDIR}/${PROJECT}"
done
