# Application values directory

Directory to store group independent values.yaml files for applications that are based on a shared
chart (for example olm-operator) and therefore do not have a dedicated helm chart directory below
`projects/<project>/applications/`.

## Example

Given the following application entry in `instances/.../clusters.yaml` or `instances/.../cluster-group-applications.yaml`
```
      - name: "gitops-operator"
        sharedChart: "olm-operator"
        namespace: gitops-operator
        project: "default"
```

The group independet values.yaml file for this application would be: `projects/default/values/applications/gitops-operator.yaml`.
