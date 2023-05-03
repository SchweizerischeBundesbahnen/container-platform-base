# Tools Installation

The following guides will show how to install the necessary tools for a an unprivileged user. It's assumed that `~/.local/bin` is part of the user's `$PATH`.

It's also possible to install them system wide with the root user. In this case you might want to use `/usr/local/bin`.

## Helm

Helm releases are published at: https://github.com/helm/helm/releases

**IMPORTANT:** Make sure you choose a helm-3.x release

```shell
$ HELM_VERSION=v3.10.3
$ wget -O /tmp/helm-${HELM_VERSION}-linux-amd64.tar.gz https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz
$ tar -C /tmp -xf /tmp/helm-${HELM_VERSION}-linux-amd64.tar.gz linux-amd64/helm
$ cp -p /tmp/linux-amd64/helm ~/.local/bin/helm
$ chmod +x ~/.local/bin/helm
$ rm -rf /tmp/helm-${HELM_VERSION}-linux-amd64.tar.gz /tmp/linux-amd64
```

Test your `helm` installation:
```
$ helm version
version.BuildInfo{Version:"v3.10.3", GitCommit:"835b7334cfe2e5e27870ab3ed4135f136eecc704", GitTreeState:"clean", GoVersion:"go1.18.9"}
```

For more information check the official [Helm documentation](https://helm.sh/)


## SOPS

SOPS releases are published at: https://github.com/mozilla/sops/releases

```shell
$ SOPS_VERSION=v3.7.3
$ wget https://github.com/mozilla/sops/releases/download/${SOPS_VERSION}/sops-${SOPS_VERSION}.linux -O ~/.local/bin/sops
$ chmod +x ~/.local/bin/sops
```

Test your `sops` installation:
```shell
$ sops --version
sops 3.7.3 (latest)
```
