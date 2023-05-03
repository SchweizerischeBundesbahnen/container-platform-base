{{/*
  Output a valid ~/.docker/config.json with the format:

  "auths": {
    "<url>": {
      "auth": "<base64(<username>:<password>)>",
      "email": "<email>",
      "password": "<password>",
      "username": "<username>
    }
  }

  See https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets

*/}}
{{- define "openshift-project.dockerconfigjson" -}}
{{- $auths := (dict) }}
{{- range $name,$config := . }}
{{- $auth := dict "auth" (printf "%s:%s" $config.auth.username $config.auth.password | b64enc) }}
{{- if $config.auth.email }}
{{- $_ := deepCopy (dict "email" $config.auth.email) | mergeOverwrite $auth }}
{{- end }}
{{- $_ := deepCopy (dict "password" $config.auth.password) | mergeOverwrite $auth }}
{{- $_ := deepCopy (dict "username" $config.auth.username) | mergeOverwrite $auth }}
{{- $_ := deepCopy (dict $config.auth.url $auth) | mergeOverwrite $auths }}
{{- end }}
{{- $cfg := dict "auths" $auths }}
{{- $cfg | toJson }}
{{- end }}
