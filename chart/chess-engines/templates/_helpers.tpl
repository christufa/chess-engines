{{- define "chess-engines.labels" -}}
app.kubernetes.io/name: chess-engines
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "chess-engines.selector" -}}
app.kubernetes.io/name: chess-engines
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "chess-engines.image" -}}
{{- $image := required "image is required (a digest-pinned reference)" .Values.image }}
{{- if not (regexMatch "@sha256:[0-9a-f]{64}$" $image) }}
{{- fail "image must be pinned by digest (…@sha256:<64 hex>)" }}
{{- end }}
{{- $image }}
{{- end }}
