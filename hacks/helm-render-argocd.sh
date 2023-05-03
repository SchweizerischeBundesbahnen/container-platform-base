#!/bin/bash
#
# Small script that renders the Helm template of the ArgoCD application
# 'argocd-instance-apps' for each instance.
#
set -exo pipefail
pushd instances >/dev/null
for chartyaml in $(find . -name 'Chart.yaml'); do
    instance=$(dirname "${chartyaml}")
    find "${instance}" -maxdepth 1 -iname '*.yaml' | grep -v Chart.yaml | xargs printf "-f %s " | xargs helm template "${instance}" >/dev/null
done
