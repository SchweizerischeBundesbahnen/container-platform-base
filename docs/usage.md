# Usage Guide

Here the most common topics related to this ArgoCD/Helm Chart repository should be explained.


## Create a new ArgoCD application

When developing a new ArgoCD `Application` you likely want to have it applied to a single test cluster during deployments (before it's merged to the master branch) so that you can see if everything works as expected. So you need to specify:

* ArgoCD instance that manages the application
* ArgoCD project that the application belongs to
* Name of the new application
* Namespace where the application will be deployed
* API of the cluster
* Git development branch where your work-in-progress code will be pushed

The individual steps needed for applying your development branch via ArgoCD are as followed:

1. Create a Git merge request that will trigger ArgoCD to create your work-in-progress application. For an application called "myapp" in the `default` project you would update `instances/<instance>/clusters.yaml` and add a new entry in the `applications` list of the involved cluster. Note that the branch name of this pull request must be different than the branch name that is eventually used for your application deployment because it must be merged before you can start developing your application:

```yaml
clusters:
  - name: "cluster-a"
    [...]
    applications:
      - name: "myapp"
        namespace: "myapp-namespace"
        revision: "feature/myapp"
```
IMPORTANT: The workflow with such a work-in-progress branch is only valid if the code owner has the same permissions as ArgoCD (i.e. cluster admins). For applications in the context of a dedicated ArgoCD project this procedure cannot be used because it would allow the execution of un-reviewed Helm code with high privileges.

2. After the project changes are merged to the `master` branch they need to be synchronized in ArgoCD. For the `default` project this would be the `argocd-instance` application.
3. A new ArgoCD application `myapp-cluster-a` should have been created. It obviously cannot be synchronized to the involved cluster yet because there is no "feature/myapp" branch nor the corresponding application yet.
4. Create the branch that was specified in the project values above (e.g. "feature/myapp") and switch to this branch. From now on the development of the application will be done in this branch.
5. Change to the `projects/default/applications` (assuming your application is assigned to the "default" project) directory of this repository and create a new Helm Chart. Important: The application name must correspond with the name specified in the project values:
```
$ helm create myapp
```
6. A new directory with a [Helm Chart](https://helm.sh/docs/topics/charts/) skeleton for your new application was created. The main components are the `Charts.yaml` that contains metadata about the chart, the `values.yaml` that will store the default [values](https://helm.sh/docs/chart_template_guide/values_files/) used by the templates and the `templates/` folder where you must place the [Helm templates](https://helm.sh/docs/chart_template_guide/) that finally generate the Kubernetes resources. There is also a `charts/` directory which is meant to be used for referencing other Helm charts that the application is depending on. In most cases this folder can be deleted. The `values.yaml` is already pre-filled with (example) variables to guide what should be parametrized in the templates. The variables that are not needed can be deleted.

7. Once an initial template is ready, it can be rendered locally to see if there are some syntax errors. This can be tested by running:
```
$ helm template .
```

8. If the template is rendered properly it can be commited to the git repository and then pushed to the origin. A few minutes later or after a manual refresh of the ArgoCD application (e.g. "myapp-cluster-a") it will change to the status `OutOfSync` and show the differences to the probably empty state in the cluster.
9. Now you can continue developing and pushing to the development branch and immediately test the changes on a live cluster.
10. Once the application is properly tested and ready to be merge to the "master" branch the last commit should remove the branch (`revision` attribute) from the application definition done in step 1. For this you have to ensure that the commit is available in your development branch (e.g. "feature/myapp"). If this is not the case rebase the development branch onto "master":
```
$ git rebase master
```
11. Before the final merge, check if the application can be moved to a group instead of assigning it to individual clusters. Each cluster has a list of groups assigned:

```yaml
clusters:
  - name: "cluster-a"
    [...]
    groups:
      - platform/ocp4
      - stage/dev
      - cloud/aws
```

If an application is assigned to one of these cluster groups in the `cluster-group-applications.yaml` file, it will automatically be deployed on all clusters that have this group assigned. If an application is assigned to a group, it no longer needs to be listed in the "applications" field of individual clusters.

```yaml
clusterGroupApps:
  [...]
  stage/dev:
    applications:
      - name: "myapp"
        namespace: "myapp-namespace"
```

## Create a new ArgoCD project

A new ArgoCD project requires a certain directory structure below the [projects](projects) directory and some symlinks in each instance directory below [instances](instances). To create the required structures, create a new branch and call `hacks/new-project.sh <project-name>`. After that, add the project to the instance by defining it in the `projects.yaml` file of the instance. Finally, create a PR and merge the new project to the "master" branch.

Note: the "groups" used in the project definition refer to SSO groups.

After the project has been created, new applications can be created in the `project/<project-name>/applications` directory, similar to the way an application in the "default" project would be created. The only difference is that all non-default-project applications need to specify the project explicitely when defining the application in the `clusters.yaml` or `cluster-group-applications.yaml` file of the instance.

### *-environment apps for dedicated ArgoCD projects

In most cases, projects that have a dedicated ArgoCD project need some basic environment that includes namespaces, roles/clusterroles etc. To provide the project with such an environment, define an `<project>-environment` application for the clusters of the project based on the `shared/charts/namespace-skeleton` shared chart. The easiest way to do this is to create a cluster-group-application for the project like this...:

```yaml
  project/<project>:
    applications:
      - name: "<project>-environment"
        sharedChart: "namespace-skeleton"
        project: "<project>"
    excludes: []
```

...and then assign the `project/<project>` group to each cluster belonging to the project.

After this the project environment can be managed by creating a `projects/<project>/values/applications/<project>-environment.yaml` values file for project global values (e.g. to define namespaces that should be present on all clusters) or by creating cluster / group specific value files. Check `shared/charts/namespace-skeleton/values.yaml` on what options are available to define the environment. Most commonly you will set `.namespaceDefaults.annotations` (to define the contact-email annotations etc.) and `.namspaceDefaults.rbac` globally for the project. The `.namespaces` value can then be managed by the project itself on a cluster-by-cluster level.
