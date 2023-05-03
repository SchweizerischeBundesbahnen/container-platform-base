# olm-operator Helm Chart

This Helm chart allows the management of an [OpenShift Livecycle Manager]()-managed operator installation, configuration and update via GitOps workflow.


## Requirements

No specific platform requirements.


### Compatibility

* OpenShift Version >= 4


## Usage Notes

The default [values.yaml](values.yaml) of the chart does not define any operator setups by default.

If you only need to manage the operator with this Helm chart it can be used directly via an [application-specific values](../../../projects/default/values/applications) file.

Alternatively the Helm chart can be used as a dependency in an umbrella chart that would define additional resources that will be managed by the operator. In this case it can be referenced in the `Chart.yaml` as following:

```yaml
dependencies:
- name: olm-operator
  version: ~1
  repository: "file://../../../../shared/charts/olm-operator"
```


## Configuration and Examples

Because the chart doesn't define any operator in its default values you must define at least the following parameters of the `operatorInstanceDefaults` value:

* `operatorGroup`: Define the name and optional access restrictions. E.g.:
```
operatorInstanceDefaults:
  operatorGroup:
    name: "gitops-operator"
    global: true
```

* `subscription`: Details of the operator that should be installed. E.g.:
```
operatorInstanceDefaults:
  subscription:
    name: openshift-gitops-operator
    spec:
      channel: stable
      installPlanApproval: Manual
      name: openshift-gitops-operator
      config:
        env:
          - name: 'DISABLE_DEFAULT_ARGOCD_INSTANCE'
            value: 'true'
      source: redhat-operators
      sourceNamespace: openshift-marketplace
```
The Subscription allows a minimal customization of the operator deployment via `.spec.config`. See the [Configuring Operators deployed by OLM](https://github.com/operator-framework/operator-lifecycle-manager/blob/master/doc/design/subscription-config.md) documentation which configurations are supported.

Once the operator deployment is defined through a Subscription you must specify where to install the operator. This can be one or multiple namespaces defined in `operatorInstances`. E.g.:
```
operatorInstances:
  gitops-operator: {}
```

All parameters of an operator installation can be adjusted per namespace. For more customization options check the comments in the [values.yaml](values.yaml)
