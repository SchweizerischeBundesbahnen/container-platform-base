# namespace-skeleton Helm Chart

This Helm chart can manage one or multiple namespaces and generic resources related to the namespace configuration. The goal of this chart is to provide a standardized Helm templates that can be used for the namespace definition of applications that live in their own namespaces.

So far the following Kubernetes resource types are supported:
* Namespace annotations
* Namespace labels
* Various RBAC-related resources such as Roles and RoleBindings
* Image registry pull/push secrets
* NetworkPolicies
* LimitRange
* ResourceQuota

Application-specific resources such as ConfigMaps and Deployments are not in the scope of this Helm chart.


## Requirements

The Kubernetes SDN plugin must support [NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) otherwise the corresponding default configuration must be adjusted.


## Compatibility

* OpenShift Version 3.11
* OpenShift Version >= 4


## Usage Notes

The default [values.yaml](values.yaml) of the chart does not define any namespaces by default.

If the Kubernetes resource Helm templates are sufficient for an application this Helm chart can be used directly via an [application-specific values](../../../projects/default/values/applications) file.

Alternatively the Helm chart can be used as a dependency in an umbrella chart that would define additional resources such as ConfigMaps, Deployments and so on. In this case it must be referenced in the `Chart.yaml` as following:

```yaml
dependencies:
- name: namespace-skeleton
  version: ~1
  repository: "file://../../../../shared/charts/namespace-skeleton"
```


## Configuration and Examples

If the chart is used with a separate `values.yaml` at least the `namespaces` dictionary must be defined. In the simplest possible definition it would just need the names of the namespaces to be created:

```yaml
namespaces:
  namespace-a: {}
  namespace-b: {}
```

It is also possible to use templates as namespace names:

```yaml
namespaces:
  "{{ .Release.Namespace }}": {}
```

This example would effectively result in the management of the namespace provided to helm as parameter (i.e. `helm template -n xxx`).

Resources that should be defined equally in all mentioned namespaces can be defined in the `namespaceDefaults` value. However, all defaults can also be overwritten per namespace which allows a lot of flexibility for all possible use cases.
```yaml
namespaceDefaults:
  annotations:
    collectord.io/logs-output: "splunk::prod"
    collectord.io/logs-index: "my_splunk_index"
```

For more customization options check the comments in the [values.yaml](values.yaml)
