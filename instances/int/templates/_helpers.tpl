{{/*
  "test.mergeDictListsByKey" merges two lists of dictionaries by comparing the contents of
  a key for each item of both lists. If both lists contain an element with the same key, both elements
  are merged with the element in the second list overriding values of the element of the first list.
  The template expects a list with 3 elements: the key name, the first list and the second list.
  It returns a dictionary with a single key "result" containing the merged list.

  It is possible to have multiple elements with the same key in both lists. Each element with key X
  in the first list will have all elements with key X in the second list merged on top of it, in the order
  they are appearing in the second list. The result list will have as many elements with key X as the
  first list had. Very simple example: given [ "a", "b" ] and [ "x", "y", "z" ] would result in
  [ "axyz", "bxyz" ] (pseudocode example, the template merges lists of dicts not lists of strings)

  Example:
    $mergeResult := include "openshift-machineset.mergeDictListsByKey" (tuple "name" $first $second) | fromYaml
    $result = get $mergeResult "result"
*/}}
{{- define "cluster.mergeDictListsByKey" -}}
  {{- $key := index . 0 -}}
  {{- $listA := index . 1 -}}
  {{- $listB := index . 2 -}}
  {{- $result := (list) -}}

  {{/*
    first pass: copy all items that are in listA and not in listB and
    merge all items that exist in both lists
  */}}
  {{-  range $listAItem := $listA -}}
    {{- $resultItem := deepCopy $listAItem }}
    {{- range $listBItem := $listB -}}
      {{- $listAItemName := get $listAItem $key -}}
      {{- $listBItemName := get $listBItem $key -}}

      {{- if eq $listAItemName $listBItemName -}}
        {{- $resultItem = mergeOverwrite $resultItem $listBItem -}}
      {{- end -}}
    {{- end -}}

    {{- $result = append $result $resultItem -}}
  {{- end -}}

  {{/*
    second pass: copy all items that are only in listB
  */}}
  {{-  range $listBItem := $listB -}}
    {{- $found := false -}}
    {{- range $resultItem := $result -}}
      {{- $listBItemName := get $listBItem $key -}}
      {{- $resultItemName := get $resultItem $key -}}

      {{- if eq $listBItemName $resultItemName -}}
        {{- $found = true -}}
      {{- end -}}
    {{- end -}}

    {{- if not $found -}}
      {{- $result = append $result $listBItem -}}
    {{- end -}}
  {{- end -}}

  {{- dict "result" $result | toYaml -}}
{{- end -}}

{{/*
  "application.values" expects a list with 3 elements: the project name of the application, the application name,
  and the root .Files object. It then checks if there exists an application specific values file for the given application. If so,
  it returns the filename (without path!) and if not an empty string.
*/}}
{{- define "application.values" -}}
  {{- $project := index . 0 -}}
  {{- $application := index . 1 -}}
  {{- $files := index . 2 -}}
  {{- $file := printf ".project-values/%s/applications/%s.yaml" $project $application -}}
  {{- with $files.Get $file -}}
    {{- printf "applications/%s.yaml" $application -}}
  {{- end -}}
{{- end -}}

{{/*
  "application.secrets" expects a list with 3 elements: the project name of application, the application name,
  and the root .Files object. It then checks if there exists an application specific secrets file. If so,
  it returns the filename (without path!) and if not an empty string.
*/}}
{{- define "application.secrets" -}}
  {{- $project := index . 0 -}}
  {{- $application := index . 1 -}}
  {{- $files := index . 2 -}}
  {{- $file := printf ".project-values/%s/applications/secrets-%s.yaml" $project $application -}}
  {{- with $files.Get $file -}}
    {{- printf "applications/secrets-%s.yaml" $application -}}
  {{- end -}}
{{- end -}}

{{/*
  "cluster.values" expects a list with 4 elements: the project name of the application, the cluster name, the application name,
  and the root .Files object. It then checks if there exists a cluster specific values file for the given application. If so,
  it returns the filename (without path!) and if not an empty string.
*/}}
{{- define "cluster.values" -}}
  {{- $project := index . 0 -}}
  {{- $cluster := index . 1 -}}
  {{- $application := index . 2 -}}
  {{- $files := index . 3 -}}
  {{- $file := printf ".project-values/%s/clusters/%s/%s.yaml" $project $cluster $application -}}
  {{- with $files.Get $file -}}
    {{- printf "clusters/%s/%s.yaml" $cluster $application -}}
  {{- end -}}
{{- end -}}

{{/*
  "cluster.secrets" expects a list with 4 elements: the project name of application, the cluster name, the application name,
  and the root .Files object. It then checks if there exists a cluster specific secrets file for the given application. If so,
  it returns the filename (without path!) and if not an empty string.
*/}}
{{- define "cluster.secrets" -}}
  {{- $project := index . 0 -}}
  {{- $cluster := index . 1 -}}
  {{- $application := index . 2 -}}
  {{- $files := index . 3 -}}
  {{- $file := printf ".project-values/%s/clusters/%s/secrets-%s.yaml" $project $cluster $application -}}
  {{- with $files.Get $file -}}
    {{- printf "clusters/%s/secrets-%s.yaml" $cluster $application -}}
  {{- end -}}
{{- end -}}

{{/*
  "group.values" expects a list with 4 elements: the project name of the application, the group name, the application name,
  and the root .Files object. It then checks if there exists a group specific values file for the given application. If so,
  it returns the filename (without path!) and if not an empty string.
*/}}
{{- define "group.values" -}}
  {{- $project := index . 0 -}}
  {{- $group := index . 1 -}}
  {{- $application := index . 2 -}}
  {{- $files := index . 3 -}}
  {{- $file := printf ".project-values/%s/groups/%s/%s.yaml" $project $group $application -}}
  {{- with $files.Get $file -}}
    {{- printf "groups/%s/%s.yaml" $group $application -}}
  {{- end -}}
{{- end -}}

{{/*
  "group.secrets" expects a list with 4 elements: the project name of the application, the group name, the application name,
  and the root .Files object. It then checks if there exists a group specific secrets file for the given application. If so,
  it returns the filename (without path!) and if not an empty string.
*/}}
{{- define "group.secrets" -}}
  {{- $project := index . 0 -}}
  {{- $group := index . 1 -}}
  {{- $application := index . 2 -}}
  {{- $files := index . 3 -}}
  {{- $file := printf ".project-values/%s/groups/%s/secrets-%s.yaml" $project $group $application -}}
  {{- with $files.Get $file -}}
    {{- printf "groups/%s/secrets-%s.yaml" $group $application -}}
  {{- end -}}
{{- end -}}

{{/*
  "group.applications" expects a list with 2 elements: a list of groups (the clusterGroups) and a dictionary
  where each key represents a group of applications (the clusterGroupApps). E.g.
  clusterGroupApps:
    <groupName>:
      applications: []
      excludes: []

  "applications" is a list of cluster applications in the same format as can be specified on a
  per cluster basis. "excludes" is a list of application names that should be excluded.

  "group.applications" merges all applications beloging to the provided "clusterGroups", while
  removing the groups listed as excludes in the "excludes" field of the application group.

  Excludes are only applied to already processed clusterGroupApps, e.g. given the following setup:
  clusterGroups:
    - group1
    - group2
    - group3
  clusterGroupApps:
    group1:
      applications:
        - name: app1
    group2:
      applications:
        - name: app2
      excludes:
        - app1
    group3:
      applications:
        - name: app3
        - name: app1
      excludes:
        - app2

  would return
  result:
    - name: app3
    - name: app1
  as group2 excludes app1 but app3 re-adds it.

  Changing the order of the cluster groups would change the result. Keeping the above clusterGroupApps
  but changing the clusterGroups as follows
  clusterGroups:
    - group1
    - group3
    - group2

  would give the following
  result:
    - name: app2
    - name: app3
  Although group3 excludes app2, the exclude does not apply as app2 is not part of the list of
  applications when group3 is processed. And app1 gets removed because group2 gets processed last.
*/}}
{{- define "group.applications" -}}
  {{- $clusterGroups := default list (index . 0) -}}
  {{- $clusterGroupApps := default (dict) (index . 1) -}}
  {{- $apps := default (list) -}}
  {{- range $group := $clusterGroups -}}
    {{- $groupApps := default (list) (default (dict) (get $clusterGroupApps $group)).applications -}}
    {{- $groupAppExcludes := default (list) (default (dict) (get $clusterGroupApps $group)).excludes -}}

    {{- with $groupApps -}}
      {{- $mergeResult := include "cluster.mergeDictListsByKey" (tuple "name" $apps .) | fromYaml -}}
      {{- $apps = get $mergeResult "result" -}}
    {{- end -}}

    {{- with $groupAppExcludes -}}
      {{- $excludes := . -}}
      {{- $filteredApps := list -}}
      {{- range $app := $apps -}}
        {{- if not (has $app.name $excludes) -}}
          {{- $filteredApps = append $filteredApps $app -}}
        {{- end -}}
      {{- end -}}
      {{- $apps = $filteredApps -}}
    {{- end -}}
  {{- end -}}

  {{- dict "result" $apps | toYaml -}}
{{- end -}}

{{/*
  "internal.dfs" implements a Depths First Search based on
  https://favtutor.com/blogs/depth-first-search-python
  It uses the fact that the context given to a named template
  is just a reference and can therefore used to hand values back
  to the caller in its parameters, without the need for an explicit
  return value.

  The template expects to be called with a named map variable as follows:

  {{- $params := dict "visited" (list) "graph" .Values.base "node" "group/name" -}}
  {{- include "internal.dfs" $params -}}

  The resulting group list can then be accessed via
  {{ $params.visited }}
*/}}
{{- define "internal.dfs" -}}
  {{- $params := . -}}
  {{- $visited := .visited -}}
  {{- $graph := .graph -}}
  {{- $node := .node -}}
  {{- if not (has $node $visited) -}}
    {{- $visited = append $visited $node -}}
    {{- $_ := set . "visited" $visited -}}
    {{- $nodeData := default (dict) (get $graph $node) -}}
    {{- $nodeGroups := default (list) $nodeData.groups -}}
    {{- range $neighbor := $nodeGroups -}}
      {{- $_ := set $params "node" $neighbor -}}
      {{- include "internal.dfs" $params -}}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/*
  "cluster.resolve_nested_groups" uses the list of groups assigned
  to a cluster and the clusterGroupApps to resolve nested groups
  in the clusterGroupApps.
*/}}
{{- define "cluster.resolve_nested_groups" -}}
  {{- $clusterGroups := index . 0 -}}
  {{- $clusterGroupApps := index . 1 -}}
  {{- $params := dict "visited" (list) "graph" $clusterGroupApps  -}}
  {{- range $group := $clusterGroups -}}
    {{- $_ := set $params "node" $group -}}
    {{- include "internal.dfs" $params -}}
  {{- end -}}
  {{- dict "result" $params.visited | toYaml -}}
{{- end -}}
