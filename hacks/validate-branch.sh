#!/bin/sh
#
# Small hackish script that verifies if someone tries to define an ArgoCD application in the non-default project
# that points to a non-master branch. This would allow unreviewed code injection and therefore we cannot allow this.
#
# Maybe this should be added later to a new function 'render.py lint' or something but as a quick fix this works too.

set -x
rc=0
for file in $(ls instances/int/cluster*.yaml instances/prod/cluster*.yaml); do
    applications=$(cat "${file}" | yq -r '.clusters.[].applications[] | select(has("revision")) | select(has("project")) | .name')
    if [ -n "${applications}" ]; then
        for app in ${applications}; do
            echo "ERROR[${file}]: Application '${app}' is part of a ArgoCD project and defines a feature branch which is not allowed"
        done
        rc=1
    fi
    applications=$(cat "${file}" | yq -r '.clusterGroupApps.[].applications[] | select(has("revision")) | select(has("project")) | .name')
    if [ -n "${applications}" ]; then
        for app in ${applications}; do
            echo "ERROR[${file}]: Application '${app}' is part of a ArgoCD project and defines a feature branch which is not allowed"
        done
        rc=1
    fi
done
exit $rc
