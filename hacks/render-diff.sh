#!/bin/bash
#
# Simple script to create application diffs between branches of the ocp-argocd repository
#
# Examples:
#   * render-diff ".*" ".*" master feature/foo .
#     -> diff of render all apps on all clusters in all stages between the master and the "feature/foo" branch
#   * render-diff feature/foo
#     -> shorthand for the previous command
#   * render-diff.sh "imon02t" "router" master feature/foo . dev,int
#     -> diff of the router app on the imon02t cluster in the dev and int stage between the master and the "feature/foo" branch

if [ $# -eq 1 ]; then
    CLUSTER_REGEX=".*"
    APP_REGEX=".*"
    SRC_BRANCH="master"
    DEST_BRANCH="${1}"
    OUT_DIR="$(realpath .)"
    STAGES="dev int prod"
else
    if [ $# -lt 5 ]; then
        echo "Usage: ${0} <cluster regex> <app regex> <source branch> <dest branch> <output dir> [stages, comma separated]"
    fi

    CLUSTER_REGEX="${1}"
    APP_REGEX="${2}"
    SRC_BRANCH="${3}"
    DEST_BRANCH="${4}"
    OUT_DIR="$(realpath "${5}")"
    STAGES=$(echo -n "${6:-"dev,int,prod"}" | tr ',' ' ')
fi

GIT_ROOT=$(realpath "$(dirname "${0}")/.." )
cd "${GIT_ROOT}"

ORIG_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
function cleanup {
    git checkout "${ORIG_BRANCH}"
}

trap cleanup INT EXIT

git checkout "${SRC_BRANCH}"

if ! [ -d "${OUT_DIR}" ]; then
    mkdir "${OUT_DIR}"
fi

for stage in ${STAGES}
do
    ./hacks/render.py --instance=${stage} render "${CLUSTER_REGEX}" "${APP_REGEX}" > "${OUT_DIR}/${stage}-src.yaml"
done

git checkout "${DEST_BRANCH}"

for stage in ${STAGES}
do
    ./hacks/render.py --instance=${stage} render "${CLUSTER_REGEX}" "${APP_REGEX}" > "${OUT_DIR}/${stage}-dest.yaml"
done

for stage in ${STAGES}
do
    diff -uw "${OUT_DIR}/${stage}-src.yaml" "${OUT_DIR}/${stage}-dest.yaml" > "${OUT_DIR}/${stage}.diff"
done
