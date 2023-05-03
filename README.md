# OpenShift Container Platform - ArgoCD Resources

This repository stores the [ArgoCD](https://argoproj.github.io/argo-cd/) [project](https://argoproj.github.io/argo-cd/operator-manual/declarative-setup/#projects) and [application](https://argoproj.github.io/argo-cd/operator-manual/declarative-setup/#applications) definitions used to manage a multi-cluster multi-cloud setup of OpenShift 4. It follows the [App of Apps](https://argoproj.github.io/argo-cd/operator-manual/declarative-setup/#app-of-apps) pattern promoted by ArgoCD that defines each application configuration and its management within ArgoCD in a delarative way via GitOps workflow. This allows a simple bootstrapping of all involved resources and a single place of change.

The repository is not a standalone project and primarly intended as a reference / example.

## Repository Structure

The repository layout is structured as following:

### Documentation

* [Usage Guide](docs/usage.md)
* [Tools Installation](docs/tools.md) (`helm`, `sops`)


### ArgoCD Instances

This git repository is used by multiple ArgCD instances, each managing their own set of ArgoCD projects and applications.

For each instance there is a subdirectory named after the instance in the [instances](instances) folder. Each instance is defined as a [Helm Chart](https://helm.sh/docs/topics/charts/) which allows a flexible definition of applications / projects thanks to templating.

Projects and applications are managed via ArgoCD-specific Custom Resource Definitions (CRD) called: `AppProject` and `Application`. These resources configure ArgoCD itself, namely which applications are synchronized to which clusters, and are only applied to the cluster where the ArgoCD server is running.

```
instances/<instance-name-a>/Chart.yaml
                           /templates/approject.yaml
                           /templates/applications.yaml
                           /values.yaml
                           /cluster-group-applications.yaml
                           /clusters.yaml
                           /projects.yaml
instances/<instance-name-b>/Chart.yaml
                           /templates/approject.yaml
                           /templates/applications.yaml
                           /values.yaml
                           /cluster-group-applications.yaml
                           /clusters.yaml
                           /projects.yaml
```

The configuration of each instance defines which clusters and projects it manages, and which application is assigned to which clusters and which project.

### ArgoCD AppProjects and Applications

Each project has its own set of applications and values, located in the `projects/<project-name>` folder.

**default Project**

If an application has no explicit project assigned in the configuration, it is automatically assigned the default project. The Helm chart for an application in the default project must be located in the `projects/default/applications` folder.

**Cluster specific applications vs. group specific applications**

To deploy an application, it must be assigned to a cluster. This can either be done by assigning the application directly to one or more clusters, which can be done in the `clusters.yaml` of the corresponding instance or the application can be assigned to a cluster group, which would result in the application being assigned to all clusters belonging to the group. This can be done in the `cluster-group-applications.yaml` file of corresponding instance. Have a look at the comments in these files for details.


### Cluster Configuration and Deployments

The Kubernetes resources for an individual application are stored in an individual subdirectory per application in the `applications` folder of a project.  depending on the complexity of the application configuration this directory might store plain YAML files that cannot be parametrized or again Helm charts that can be customized with cluster-specific variables.

```
applications/<application-name-1>/Chart.yaml
                                 /templates/resource-a.yaml
                                 /templates/resource-b.yaml
                                 /templates/resource-c.yaml
                                 /values.yaml
                                 /secrets.yaml
applications/<application-name-2>/Chart.yaml
                                 /templates/resource-d.yaml
                                 /templates/resource-e.yaml
                                 /values.yaml
```
It's also possible to add encrypted value files that store credentials and must be called `secrets.yaml`.


### Cluster-specific Variables

The application parametrization for an individual cluster is defined in cluster-specific sub-directories in the `values/clusters` folder of the project. Each cluster will contain multiple YAML files ([Helm Value files](https://helm.sh/docs/chart_template_guide/values_files/)) that contain the values for an individual application.

```
values/clusters/<cluster-a>/<application-name-1>.yaml
                           /<application-name-2>.yaml
values/clusters/<cluster-b>/<application-name-1>.yaml
                           /<application-name-2>.yaml
```

### Group-specific Variables

Each cluster can have and arbitrary number of groups assigned (see comments/examples in the values.yaml files of the different [instances](instances)). Similar to the application parametrization for individual clusters (see above), each group has a group specific sub-directory in the `values/groups` folder of the project. Each group will contain multiple YAML files ([Helm Value files](https://helm.sh/docs/chart_template_guide/values_files/)) that contain the values for an individual application.

```
values/groups/<group-a>/<application-name-1>.yaml
                       /<application-name-2>.yaml
values/groups/<group-b>/<application-name-1>.yaml
                       /<application-name-2>.yaml
```

It is possible to define nested groups that have values in sub-directories below another group folder.

```
values/groups/<group-a>/<group-c>/<application-name-1>.yaml
                                 /<application-name-2>.yaml
values/groups/<group-b>/<group-d>/<application-name-1>.yaml
                                 /<application-name-2>.yaml
```

In addition to this, each group folder can contain a `common.yaml` file that will be added to all applications deployed on a cluster that has the group assigned:

```
values/groups/<group-a>/<application-name-1>.yaml
                       /<application-name-2>.yaml
                       /common.yaml
values/groups/<group-b>/<group-d>/<application-name-1>.yaml
                                 /<application-name-2>.yaml
                                 /common.yaml
```

Common values have a lower priority than application specific values _in the same group_ and will be overriden by them.

An ArgoCD `Application` will then use the Kubernetes resource templates defined in a specific application directory and apply the cluster- and group-specific variables from the corresponding values files to generate the final resource definition that is synchronized to the cluster.

When using cluster- or group-specific secrets, the encrypted values file must be called `secrets-<application-name>.yaml`.
See https://github.com/camptocamp/helm-sops#Usage

### Secrets

Encrypted value files are supported by using an ArgoCD image based on https://github.com/camptocamp/docker-argocd (or any other image containing a properly set-up https://github.com/camptocamp/helm-sops). If done correctly, wherever a `values.yaml` or `<appname>.yaml` file is used, an additional `secrets.yaml` or `secrets-<appname>.yaml` file can be used. These yaml files are expected to be SOPS encrypted (see [Tools Installation](docs/tools.md) for information regarding SOPS).

## Helm Chart Rendering

Custom arguments used by ArgoCD to render the Helm chart are defined in the `Application` Kubernetes resource under `spec.source.helm`: under `spec.source.helm`. E.g.:

```
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: grafana-cluster-a
  namespace: platform-argocd
spec:
  destination:
    namespace: openshift-monitoring
    server: https://api.cluster-a.sbb.ch:6443
  project: default
  source:
    helm:
      parameters:
        - name: argocdParams.clusterName
          value: cluster-a
        - name: argocdParams.clusterAPI
          value: api.cluster-a.sbb.ch:6443
        - name: argocdParams.argocdStage
          value: dev
      valueFiles:
        - values.yaml
        - secrets.yaml
        - ../../values/groups/platform/ocp4/grafana.yaml
        - ../../values/clusters/cluster-a/grafana.yaml
    path: applications/grafana
    repoURL: https://github.com/schweizerischeBundesbahnen/container-platform-base.git
    targetRevision: master
```


### parameters

Additional parameters that are passed from ArgoCD to Helm via `--set key=value`. They can be accessed in a Helm chart identical to every other value (e.g. `$.Values.key`).

**Naming**

We prefix parameters that are passed from ArgoCD with `argocdParams`.

So far the following values can be used by charts in our setup:
* `argocdParams.argocdStage`: Stage of the ArgoCD instance that is applying the Helm chart (e.g. dev, test, int, prod)
* `argocdParams.clusterAPI`: The URL to the OpenShift cluster API
* `argocdParams.clusterName`: The OpenShift cluster name used by ArgoCD
* `argocdParams.buildEnv.XXX`: All the environment variables defined in the ArgoCD [build environment](https://argoproj.github.io/argo-cd/user-guide/build-environment/). Must be enabled by setting `addArgoCDBuildEnv: true` in the application definition.


### valueFiles

A list of value files that are passed to Helm. The list is generated automatically depending on the existence of group- and cluster-specific value files.

You can debug this locally by running:
```
hacks/render.py render [--debug] <app-name> <cluster-name>
```
