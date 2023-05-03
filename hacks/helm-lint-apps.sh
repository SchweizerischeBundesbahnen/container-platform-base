#!/bin/sh
#
# Small script that runs `helm lint` on all application Helm charts with
# their default values (or values-lint.yaml if it exists).
#
cd projects >/dev/null || exit 1
ret=0
failed=""
for chartyaml in $(find . -name 'Chart.yaml'); do
    application=$(dirname "${chartyaml}")
    values=""
    if [ -f "${application}/values.yaml" ]; then
        values="-f ${application}/values.yaml"
    fi
    if [ -f "${application}/values-lint.yaml" ]; then
        values="${values} -f ${application}/values-lint.yaml"
    fi
    helm lint ${values} "${application}"
    rc=$?
    echo "Return code: ${rc}"
    if [ "${rc}" != "0" ]; then
        failed="${application},${failed}"
        ret=${rc}
    fi
done
echo
if [ -n "${failed}" ]; then
    echo -e "Failed applications:\n$(echo ${failed}|tr ',' '\n')"
else
    echo "All applications linted successfully"
fi
exit ${ret}
