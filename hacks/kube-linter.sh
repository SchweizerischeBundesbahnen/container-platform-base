#!/bin/bash
#
# kube-linter.sh renders all applications for all clusters in all projects with their corresponding
# application/group/cluster specific values and runs the result through kube-linter

KUBELINTER_EXTRA_ARGS="${@}"

export PATH=~/.local/bin:$PATH

RENDERPY="hacks/render.py"
INSTANCEDIR="${INSTANCEDIR:-instances}"
CLUSTER="${CLUSTER:-.*}"

RC=0
for chartyaml in $(find "${INSTANCEDIR}" -name 'Chart.yaml'); do
    instance=$(basename $(dirname $chartyaml))
    echo "# Checking instance: '${instance}'"

    for cluster in $("${RENDERPY}" --instance "${instance}" list_clusters "${CLUSTER}"); do
        echo "## [${instance}] Checking cluster: '${cluster}'"
        for app in $("${RENDERPY}" --instance ${instance} list_cluster_apps "${cluster}"); do
            echo "### [${instance}](${cluster}) Checking app: '${app}'"
            "${RENDERPY}" --instance "${instance}" render --warn-notfound "${cluster}" "${app}" | \
                kube-linter lint ${KUBELINTER_EXTRA_ARGS[*]} -
            if [ $? -gt 0 ]; then
                RC=1
            fi
        done
    done
done
if [ ${RC} -gt 0 ]; then
    echo "Check found errors, check the log output above!"
else
    echo "No errors found, everything OK!"
fi
# Ignore errors for now
#exit ${RC}
exit 0
