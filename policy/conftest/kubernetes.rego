package main

import rego.v1

# Conftest policy for Kubernetes / Kustomize manifests.

is_workload if {
  input.kind in {"Deployment", "StatefulSet", "DaemonSet"}
}

is_job if {
  input.kind == "Job"
}

resource_name := name if {
  metadata := object.get(input, "metadata", {})
  name := object.get(metadata, "name", "<unnamed>")
}

resource_ref := ref if {
  kind := object.get(input, "kind", "<unknown-kind>")
  ref := sprintf("%s/%s", [kind, resource_name])
}

pod_spec := spec if {
  is_workload
  spec := input.spec.template.spec
}

pod_spec := spec if {
  is_job
  spec := input.spec.template.spec
}

containers contains container if {
  spec := pod_spec
  some container in object.get(spec, "containers", [])
}

containers contains container if {
  spec := pod_spec
  some container in object.get(spec, "initContainers", [])
}

workload_containers contains container if {
  is_workload
  spec := input.spec.template.spec
  some container in object.get(spec, "containers", [])
}

has_value(obj, key) if {
  object.get(obj, key, null) != null
}

container_requests(container) := requests if {
  resources := object.get(container, "resources", {})
  requests := object.get(resources, "requests", {})
}

container_limits(container) := limits if {
  resources := object.get(container, "resources", {})
  limits := object.get(resources, "limits", {})
}

deny contains msg if {
  some container in containers
  image := object.get(container, "image", "")
  endswith(image, ":latest")
  msg := sprintf("%s container %s uses mutable :latest image tag", [resource_ref, container.name])
}

deny contains msg if {
  some container in containers
  requests := container_requests(container)
  not has_value(requests, "cpu")
  msg := sprintf("%s container %s is missing CPU request", [resource_ref, container.name])
}

deny contains msg if {
  some container in containers
  requests := container_requests(container)
  not has_value(requests, "memory")
  msg := sprintf("%s container %s is missing memory request", [resource_ref, container.name])
}

deny contains msg if {
  some container in containers
  limits := container_limits(container)
  not has_value(limits, "cpu")
  msg := sprintf("%s container %s is missing CPU limit", [resource_ref, container.name])
}

deny contains msg if {
  some container in containers
  limits := container_limits(container)
  not has_value(limits, "memory")
  msg := sprintf("%s container %s is missing memory limit", [resource_ref, container.name])
}

deny contains msg if {
  some container in workload_containers
  not has_value(container, "livenessProbe")
  msg := sprintf("%s container %s is missing livenessProbe", [resource_ref, container.name])
}

deny contains msg if {
  some container in workload_containers
  not has_value(container, "readinessProbe")
  msg := sprintf("%s container %s is missing readinessProbe", [resource_ref, container.name])
}

deny contains msg if {
  some container in containers
  security_context := object.get(container, "securityContext", {})
  object.get(security_context, "privileged", false) == true
  msg := sprintf("%s container %s is privileged", [resource_ref, container.name])
}

deny contains msg if {
  some container in containers
  security_context := object.get(container, "securityContext", {})
  object.get(security_context, "allowPrivilegeEscalation", false) == true
  msg := sprintf("%s container %s allows privilege escalation", [resource_ref, container.name])
}

deny contains msg if {
  input.kind == "Kustomization"
  some generator in object.get(input, "secretGenerator", [])
  literals := object.get(generator, "literals", [])
  count(literals) > 0
  msg := sprintf("Kustomization %s uses secretGenerator literals; use envs/files from uncommitted runtime secret files or External Secrets", [resource_name])
}

is_example_secret if {
  annotations := object.get(object.get(input, "metadata", {}), "annotations", {})
  object.get(annotations, "retailops.io/example", "false") == "true"
}

is_example_secret if {
  endswith(resource_name, "-example")
}

deny contains msg if {
  input.kind == "Secret"
  not is_example_secret
  msg := sprintf("Kubernetes Secret %s is committed as a manifest; use External Secrets or uncommitted local secret files", [resource_name])
}
