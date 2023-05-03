#!/bin/bash
#
# check-all.sh renders all applications for all clusters in all projects with their corresponding
# application/group/cluster specific values.
#
# If a clustername is provided as argument only the applications of the given cluster will be rendered.
#
# Note: because it is possible und perfectly valid for applications to be listed for a cluster but
#       to only exist in a certain branch/tag, warnings about "missing" applications are to be expected.
#       The script treats these strictly as warnings because it assumes that the application exists
#       in a different branch. The script only checks the currently checked out state and does not
#       consider different git revisions.
export PATH=~/.local/bin:$PATH

RENDERPY="hacks/render.py"
INSTANCEDIR="instances"

CLUSTER="${1:-.*}"

RC=0

for chartyaml in $(find "${INSTANCEDIR}" -name 'Chart.yaml'); do
    instance=$(basename $(dirname $chartyaml))
    echo "# Checking instance: '${instance}'"

    "${RENDERPY}" --instance "${instance}" render --quiet --warn-notfound ${RENDERPY_ARGS} "${CLUSTER}"
    if [ $? -gt 0 ]; then
        RC=1
    fi
    echo
    echo
done
if [ ${RC} -gt 0 ]; then
    echo "Check found errors, check the log output above!"
else
    echo "No errors found, everything OK!"
fi
exit ${RC}
