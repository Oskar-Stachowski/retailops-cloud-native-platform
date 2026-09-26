# kindnet source

`kindnet.yaml` is from
[kubernetes-sigs/kindnet v1.0.1](https://github.com/kubernetes-sigs/kindnet/blob/v1.0.1/install-kindnet.yaml),
under the Apache-2.0 license copied as `LICENSE.kindnet`.

Local changes: image updated from the tag's v1.0.0 reference to v1.0.1, pinned by
OCI index digest; DNS caching disabled so the drill exercises the explicit
CoreDNS egress policy. The CNI requires privileged node networking and hostPath
mounts. It runs only in the uniquely owned disposable kind cluster; it is not an
application workload and is not covered by `k8s/` application Checkov exceptions.
See [upstream design](https://kindnet.sigs.k8s.io/docs/design/kindnet/).
