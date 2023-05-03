#!/usr/bin/env python3

# Documentation style according to https://realpython.com/documenting-python-code/, NumPy/SciPy docstrings format

"""Multi Cluster / Multi Application Render Tool

This script allows the user to render (i.e. create Kubernetes resource yaml documents) one or more applications (normally
in the form of Helm charts) for one or more clusters. It is specifically designed to work with the custom mono repository
used by SBB to manage the SBB Kubernetes platform, but with the exception of the actual config format/structure,
everything should be mostly configurable via cli parameters.

The need for this script comes from the fact that a helm chart not only has one, but an arbitrary number of
value files (default chart values, cluster specific values, group specific values) that are distributed over different
directories in the repository. This means the helm chart "echo-server" can have vastly different values, depending on
the cluster it should be rendered for and the groups assigned to this cluster. And each cluster can have different
sets of applications, based on the groups it has assigned. The script uses the configuration that is also used by
ArgoCD to deploy each application and executes the necessary render commands (normally "helm template") similar to
what ArgoCD would do.

The core construct is an "instance", which is basically a directory that contains the configuration consisting
of a list of clusters, applications and groups. The actual format is documented in the config itself, so check that for
details. The script always operates on a single instance, but on an arbitrary amount of applications and clusters in this
instance.

The primary function of this script is to gather all required value files for an application on a given cluster, and
execute a render command (again, normally "helm template") to produce the kubernetes resource yamls for this application.
It can do this with an arbitrary number of applications and clusters (i.e. from "render app x on cluster y" to "render all apps
for all clusters").

As Convenience functions, it also supports listing the servers currently configured for an instance, and listing the
applications one or more clusters in an instance.
"""

import argparse
import atexit
import os
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Union

import yaml

# deep_merge by https://gist.github.com/tfeldmann
# source: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9?permalink_comment_id=4038517#gistcomment-4038517
# "My version which passes this test (MIT license):"
def deep_merge(a: dict, b: dict) -> dict:
    result = deepcopy(a)
    for bk, bv in b.items():
        av = result.get("k")
        if isinstance(av, dict) and isinstance(bv, dict):
            result[bk] = deep_merge(av, bv)
        else:
            result[bk] = deepcopy(bv)
    return result


class NamingConflict(Exception):
    pass


class DirectoryLayout:
    """
    A class to model the directory structure for instances, applications and values.
    Its main function is to encapsulate all functions necessary to construct paths
    later used the other classes. The goal is to ensure that structural changes
    to the directory structure only require changes to this class.

    The default layout is as follows:

    .
    ├── instances
    │   └── test
    │       └── values.yaml
    ├── projects
    │   └── default
    │       ├── applications
    │       └── values
    │           ├── applications
    │           ├── clusters
    │           └── groups
    └── shared
        └── charts

    Attributes
    ----------
    root : str
        the root directory, below which all other directories are assumed to be
    instances : str
        the path to the directory containing all instance directories
    projects : str
        the path to the directory containing all project directories
    apps : str
        the name of the directory containing the application directories; also used
        as the name of the values folder containing application specific values
    values : str
        the name of the directory containing the cluster and group value directories
    clusters : str
        the name of the cluster values directory, containing the cluster values directories
    groups : str
        the name of the groups values directory, containing the group values directory
        structure
    common_id : str
        identifier that is used when referring to / handling values that are assigned
        to a group but not to a specific application
    shared : str
        the path to the shared charts directory, containing the helm charts that can
        be used by multiple projects
    """

    def __init__(
        self,
        root: str = ".",
        instances: str = "instances",
        projects: str = "projects",
        apps: str = "applications",
        values: str = "values",
        clusters: str = "clusters",
        groups: str = "groups",
        shared: str = "shared/charts",
    ) -> None:
        """
        Parameters
        ----------
        root : str, optional
            the path of the root directory, below which all other directories are assumed to be
        instances : str, optional
            the name of the directory containing all instance directories
        projects : str, optional
            the name of the directory containing all project directories
        apps : str, optional
            the name of the directory containing the application directories; also used
            as the name of the values folder containing application specific values
        values : str, optional
            the name of the directory containing the cluster and group value directories
        clusters : str, optional
            the name of the cluster values directory, containing the cluster values directories
        groups : str, optional
            the name of the groups values directory, containing the group values directory
            structure
        shared : str
            the path to the shared charts directory, containing the helm charts that can
            be used by multiple projects
        """
        self._root = root
        self._instances = instances
        self._projects = projects
        self._apps = apps
        self._values = values
        self._clusters = clusters
        self._groups = groups
        self._shared = shared

    @property
    def root(self) -> str:
        return self._root

    @property
    def instances(self) -> str:
        return os.path.join(self._root, self._instances)

    @property
    def projects(self) -> str:
        return os.path.join(self._root, self._projects)

    @property
    def apps(self) -> str:
        return self._apps

    @property
    def values(self) -> str:
        return self._values

    @property
    def clusters(self) -> str:
        return self._clusters

    @property
    def groups(self) -> str:
        return self._groups

    @property
    def common_id(self) -> str:
        return "common"

    @property
    def shared(self) -> str:
        return os.path.join(self._root, self._shared)

    def instance(self, instance: str) -> str:
        """Returns the path to the instance directory of a specific instance.

        Parameters
        ----------
        instance : str
            the name of the instance for which the path should be returned
        """
        return os.path.join(self.instances, instance)

    def project(self, project: str) -> str:
        """Returns the path to the project directory of a specific instance.

        Parameters
        ----------
        project : str
            the name of the project for which the path should be returned
        """
        return os.path.join(self.projects, project)

    def app(self, project: str, app: str) -> str:
        """Returns the path to the application directory of a specific application.

        Parameters
        ----------
        project : str
            the name of the project containing the application
        application : str
            the name of the application for which the path should be returned
        """
        return os.path.join(self.project(project), self.apps, app)

    def apps_addon_values(self, project: str) -> str:
        """Returns the path to the applications addon values directory of a specific group.

        Parameters
        ----------
        project : str
            the name of the project for which the group values directory should be return
        """
        return os.path.join(self.project(project), self.values, self.apps)

    def group_values(self, project: str, group: str) -> str:
        """Returns the path to the group values directory of a specific group.

        Parameters
        ----------
        project : str
            the name of the project for which the group values directory should be return
        group : str
            the name of the group for which the path should be returned
        """
        return os.path.join(self.project(project), self.values, self.groups, group)

    def cluster_values(self, project: str, cluster: str) -> str:
        """Returns the path to the cluster values directory of a specific cluster.

        Parameters
        ----------
        project : str
            the name of the project for which the cluster values directory should be return
        cluster : str
            the name of the cluster for which the path should be returned
        """
        return os.path.join(self.project(project), self.values, self.clusters, cluster)

    def group_values_file(self, project: str, group: str, file: str) -> str:
        """Returns the path to a specific file in a group values directory.

        Parameters
        ----------
        project : str
            the name of the project for which the group values directory should be return
        group : str
            the name of the group for which the path should be returned
        file : str
            the filename for which the path should be returned
        """
        return os.path.join(self.group_values(project, group), file)

    def cluster_values_file(self, project: str, cluster: str, file: str) -> str:
        """Returns the path to a specific file in a cluster values directory.

        Parameters
        ----------
        project : str
            the name of the project for which the cluster values file should be returned
        cluster : str
            the name of the cluster for which the path should be returned
        file : str
            the filename of the file for which the path should be returned
        """
        return os.path.join(self.cluster_values(project, cluster), file)

    def apps_addon_values_file(self, project: str, file: str) -> str:
        """Returns the path to a specific file in the applications addon values directory.

        Parameters
        ----------
        project : str
            the name of the project for which the applications values file should be returned
        file : str
            the filename of the file for which the path should be returned
        """
        return os.path.join(self.apps_addon_values(project), file)

    def shared_chart(self, chart: str) -> str:
        """Returns the path to the directory of a shared chart.

        Parameters
        ----------
        chart : str
            the name of the chart for which the path should be returned
        """
        return os.path.join(self.shared, chart)


class ConfigModel:
    """
    The base class for all config classes. It ensures that all config objects have a valid
    DirectoryLayout assigned, even when non is explicitly assigned when instantiating a
    config object.

    Attributes
    ----------
    layout : DirectoryLayout
        the directory layout; if no layout is assigned during instantiation, a default layout
        is created.
    """

    def __init__(self, layout: DirectoryLayout) -> None:
        """
        Parameters
        ----------
        layout : DirectoryLayout
            the DirectoryLayout to use; a default one will be created if None is provided
        """
        self._layout = layout

    @property
    def layout(self) -> DirectoryLayout:
        # if the object has a valid directory layout set, return it but
        # create a default one if not
        if hasattr(self, "_layout") and self._layout:
            return self._layout

        self._layout = DirectoryLayout()
        return self._layout

    @layout.setter
    def layout(self, layout: DirectoryLayout) -> None:
        """Set a specific DirectoryLayout

        Parameters
        ----------
        layout:
            the layout to set
        """
        self._layout = layout


class Application(ConfigModel):
    """
    The Application class represents an application as can be defined in the config
    below a cluster or a cluster group. It adheres to the "be flexible in what you
    accept and strict what you return" concept in that it just converts all keys
    of the application config dict to read-only class attributes.

    All attributes listed below are in addition to the ones extracted from the config.

    Attributes
    ----------
    exists : bool
        returns True if the application directory exists
    path : str
        the path to the application directory
    value_path : str|None
        path to the default "values.yaml" file of the application; is None
        if the application has not values.yaml file
    secrets_path : str|None
        path to the default "secrets.yaml" file of the application; is None
        if the application has not secrets.yaml file
    """

    def __init__(self, config: dict, layout: DirectoryLayout = None) -> None:
        """
        Parameters
        ----------
        config : dict
            dict representing a single application configuration (see configuration documentation for details)
        layout : DirectoryLayout, optional
            the directory layout to use
        """
        super().__init__(layout)

        self.project = "default"
        self.namespace = "default"
        for key, value in config.items():
            setattr(self, key, value)

        if self.name == self.layout.common_id:
            raise NamingConflict(
                f"An application cannot be named '{self.layout.common_id}' as this conflicts with the '{self.layout.common_id}.yaml' file of groups!"
            )

    @property
    def exists(self) -> bool:
        return os.path.isdir(self.path)

    @property
    def path(self) -> str:
        if hasattr(self, "sharedChart") and self.sharedChart:
            return self.layout.shared_chart(self.sharedChart)
        return self.layout.app(self.project, self.name)

    def file_path(self, relpath: str, must_exist: bool = False) -> Union[str, None]:
        """Returns the path to a file in the application directory.

        Parameters:
        relpath : str
            the file path relative to the application directory
        must_exist : bool, optional
            whether the return value refers to an actually existing file. If True
            and the file does not exist, None is return. In all other cases the path is returned.
        """
        path = os.path.join(self.path, relpath)
        if not must_exist:
            return path

        if os.path.isfile(path):
            return path
        return None

    def addon_file_path(
        self, relpath: str, must_exist: bool = False
    ) -> Union[str, None]:
        """Returns the path to a file in the applications addon values directory.

        Parameters:
        relpath : str
            the file path relative to the applications addon values directory
        must_exist : bool, optional
            whether the return value refers to an actually existing file. If True
            and the file does not exist, None is return. In all other cases the path is returned.
        """
        path = self.layout.apps_addon_values_file(self.project, relpath)
        if not must_exist:
            return path

        if os.path.isfile(path):
            return path
        return None

    @property
    def values_path(self) -> Union[str, None]:
        return self.file_path("values.yaml", True)

    @property
    def secrets_path(self) -> Union[str, None]:
        return self.file_path("secrets.yaml", True)

    @property
    def addon_values_path(self) -> Union[str, None]:
        return self.addon_file_path(f"{self.name}.yaml", True)

    @property
    def addon_secrets_path(self) -> Union[str, None]:
        return self.addon_file_path(f"secrets-{self.name}.yaml", True)

    def __add__(self, other):
        """Override the + operator for Application objects.

        Merges two Application objects according to the following rules:
        * scalar values and lists of the first operand are overwritten by values of the second operand
          (data types do not have to match, a string can be overwritten by a dict etc.)
        * if the second operand has a value the first operand is missing, it will be added
        * dictionary fields will be deep_merged, with the value of the first operand having
          the "lower" priority (i.e. in case of a conflict, the value in the dict of the first
          operand will be overwritten by the value in the dict of the second operand)

        This process modifies the first operand! This means it always behaves like
        "a = a + b" and not like "c = a + b". Time will tell if this can be considered a bug or
        a feature.
        """
        for key, other_value in other.__dict__.items():
            self_value = getattr(self, key, None)
            if isinstance(self_value, dict):
                new_value = deep_merge(self_value, other_value)
                setattr(self, key, new_value)
            else:
                setattr(self, key, other_value)
        return self


class ClusterGroupApps(ConfigModel):
    """
    The ClusterGroupApps class represents the "clusterGroupsApps" section of the
    config. It manages app -> group associations and can be used to retrieve all apps
    belonging to a set of groups, while factoring in the per-group excludes.

    Attributes
    ----------
    groups : dict
        each key in the "groups" attribute is the name of a group and is itself
        a dict with two keys: "applications" (dict of Applications) and "excludes"
        (list of application names).
    """

    def __init__(self, config: dict, layout: DirectoryLayout = None) -> None:
        """
        Parameters
        ----------
        config : dict
            dict representing the "clusterGroupsApps" section of the configuration (see configuraiton documentation for details)
        layout : DirectoryLayout, optional
            the directory layout to use
        """
        super().__init__(layout)
        self.groups = {}

        for name, group in config.items():
            self.groups[name] = {
                "excludes": group.get("excludes", []),
                "applications": {},
            }
            for app_config in group.get("applications", []):
                app = Application(app_config, self.layout)
                self.groups[name]["applications"][app.name] = app

    def apps(self, groups: list) -> dict:
        """
        Given a list of group names, this method returns a dictionary of applications belonging to these groups with all
        excludes applied and the application settings merged.

        The provided group list is treated as ordered by priority, with the first group being the one with the
        lowest priority. If an application is part of multiple groups, its settings will be merged, with the settings
        of the higher priority group overriding the settings of the app in the lower priority groups.

        Excludes are applied for each group individually, i.e. an exclude in a group can only remove applications
        of lower priority groups.

        Parameters
        ----------
        groups : list
            list of group names for which to retrieve the applications
        """
        result = {}
        for group in groups:
            apps = self.group_apps(group)
            excludes = self.group_excludes(group)

            for name, app in apps.items():
                if name in result:
                    result[name] = result[name] + app
                else:
                    result[name] = app

            for exclude in excludes:
                if exclude in result:
                    del result[exclude]

        return result

    def group_apps(self, group: str) -> dict:
        """Retrieves the applications for the given group.

        Parameters
        ----------
        group : str
            the name of the group for which the applications should be retrieved
        """
        return self.groups.get(group, {}).get("applications", {})

    def group_excludes(self, group: str) -> list:
        """Retrieves the list of application names the given group excludes.

        Parameters
        ----------
        group : str
            the name of the group for which the excludes should be retrieved
        """
        return self.groups.get(group, {}).get("excludes", [])


class Cluster(ConfigModel):
    """
    The Cluster class represents a cluster. Its primary task is to provide access
    to the applications belonging to the cluster and its groups as well as
    generating the paths to the different value files (cluster values, group values).
    During instantiation, it converts all keys of the provided cluster config to
    attributes.

    All attributes listed below are in addition to the ones extracted from the config or
    attributes that are changed during instantiation.

    Attributes
    ----------
    groups : list
        the list of groups that are assigned to the cluster; the first group is always "all",
        independent of the first item of the groups list in the config; if the config group list
        already starts with "all" it will not be added a second time (nevertheless it will be added
        a second time if "all" is part of the groups list aside from the first position)
    applications : dict
        a dictionary of Application objects, representing the applications assigned to this cluster;
        it contains the applications assigned directly to the cluster as well as the applications
        belonging to the groups the cluster has assigned; all cluster and group application excludes
        are applied
    """

    def __init__(
        self,
        config: dict,
        cluster_group_apps: ClusterGroupApps,
        layout: DirectoryLayout = None,
    ):
        """
        Parameters
        ----------
        config : dict
            a dict representing the configuration of a single cluster; see the configuration documentation for details
        cluster_group_apps : ClusterGroupApps
            a cluster group apps object that holds group -> application associations; it is used when retrieving
            the list of applications for this clusters
        layout : DirectoryLayout, optional
            the directory layout to use
        """
        super().__init__(layout)
        self.groups = ["all"]
        self._apps = []
        self._excludes = []
        for key, value in config.items():
            rkey = key
            rval = value
            if key == "applications":
                rkey = "_apps"
            elif key == "excludeApplications":
                rkey = "_excludes"
            elif key == "groups":
                if rval[0] == "all":
                    rval = rval[1:]
                rval = self.groups + rval
            setattr(self, rkey, rval)
        self._cluster_group_apps = cluster_group_apps

    @property
    def applications(self) -> dict:
        # lazy loading, only generate the application objects when someone tries to use them
        try:
            return self._applications
        except AttributeError:
            cluster_apps = self._cluster_group_apps.apps(self.groups)

            for app_config in self._apps:
                app = Application(app_config, self.layout)
                if app.name in cluster_apps:
                    cluster_apps[app.name] = cluster_apps[app.name] + app
                else:
                    cluster_apps[app.name] = app

            for exclude in self._excludes:
                if exclude in cluster_apps:
                    del cluster_apps[exclude]

            self._applications = cluster_apps
            return self._applications

    def select_applications(self, regex: str) -> dict:
        """
        Given a regex to be matched against application names, the method returns a dictionary of
        applications whose names match the regex.

        Parameters
        ----------
        regex: str
            a string that is treated as regex; it will be wrapped in ^$ before being compiled to
            a regex object; the method returns all applications whose name match the resulting regex
        """
        # use an r"" string here the regex module interprets
        # potential \ characters instead of python
        selector = re.compile(r"^%s$" % regex)
        result = {}
        for name, app in self.applications.items():
            match = selector.search(name)
            if match:
                result[name] = app
        return result

    # get the path for a file in the cluster value directory
    def app_cluster_values_file_paths(self, appname: str) -> list:
        """
        Returns the path to all cluster value files for the given application.

        Parameters
        ----------
        appname : str
            name of the application for which the value file should be retrieved
        """
        app = self.applications[appname]

        result = []

        default_common_values_path = self.layout.cluster_values_file(
            "default", self.name, f"{self.layout.common_id}.yaml"
        )
        default_common_secrets_path = self.layout.cluster_values_file(
            "default", self.name, f"secrets-{self.layout.common_id}.yaml"
        )
        common_values_path = self.layout.cluster_values_file(
            app.project, self.name, f"{self.layout.common_id}.yaml"
        )
        common_secrets_path = self.layout.cluster_values_file(
            app.project, self.name, f"secrets-{self.layout.common_id}.yaml"
        )
        values_path = self.layout.cluster_values_file(
            app.project, self.name, f"{appname}.yaml"
        )
        secrets_path = self.layout.cluster_values_file(
            app.project, self.name, f"secrets-{appname}.yaml"
        )

        paths = []
        if hasattr(app, "addDefaultCommonValues") and app.addDefaultCommonValues:
            paths.append(default_common_values_path)

        if hasattr(app, "addDefaultCommonSecrets") and app.addDefaultCommonSecrets:
            paths.append(default_common_secrets_path)

        paths.extend(
            [
                common_values_path,
                common_secrets_path,
                values_path,
                secrets_path,
            ]
        )

        for path in paths:
            if os.path.isfile(path):
                result.append(path)

        return result

    # get value paths relevant for the given application for one or more group values directories
    def app_group_values_file_paths(self, appname: str) -> list:
        """
        Returns the path to all value files for the given application in all groups the cluster has assigned.

        Parameters
        ----------
        appname : str
            name of the application for which the value files should be retrieved
        """
        app = self.applications[appname]

        result = []
        for group in self.groups:
            default_common_values_path = self.layout.group_values_file(
                "default", group, f"{self.layout.common_id}.yaml"
            )
            default_common_secrets_path = self.layout.group_values_file(
                "default", group, f"secrets-{self.layout.common_id}.yaml"
            )
            common_values_path = self.layout.group_values_file(
                app.project, group, f"{self.layout.common_id}.yaml"
            )
            common_secrets_path = self.layout.group_values_file(
                app.project, group, f"secrets-{self.layout.common_id}.yaml"
            )
            values_path = self.layout.group_values_file(
                app.project, group, f"{appname}.yaml"
            )
            secrets_path = self.layout.group_values_file(
                app.project, group, f"secrets-{appname}.yaml"
            )

            paths = []
            if hasattr(app, "addDefaultCommonValues") and app.addDefaultCommonValues:
                paths.append(default_common_values_path)

            if hasattr(app, "addDefaultCommonSecrets") and app.addDefaultCommonSecrets:
                paths.append(default_common_secrets_path)

            paths.extend(
                [
                    common_values_path,
                    common_secrets_path,
                    values_path,
                    secrets_path,
                ]
            )

            for path in paths:
                if os.path.isfile(path):
                    result.append(path)

        return result


class Instance(ConfigModel):
    """
    An Instance represents a complete set of configuration, including all clusters, applications, groups
    etc. belonging together.

    Its primary purpose is to load all configuration files, merge them and create a set of cluster objects.

    Attributes
    ----------
    name : str
        the name of the instance
    path : str
        the path to the instance directory, containing the configuration files
    cluster_group_apps : ClusterGroupApps
        the group -> application settings for the given instance, representing the "clusterGroupApps"
        configuration section
    config : dict
        the full instance configuration as a dictionary
    clusters : dict
        a dictionary of clusters belonging to the instace; each dictionary key is the name of a cluster
    """

    def __init__(self, name: str = "test", layout: DirectoryLayout = None):
        """
        Parameters
        ----------
        name : str, optional
            the name of the new instance
        layout : DirectoryLayout, optional
            the directory layout to use
        """
        super().__init__(layout)
        self.name = name
        if not os.path.isdir(self.path):
            raise FileNotFoundError(f"No instance directory: {self.path}")

    @property
    def path(self) -> str:
        return self.layout.instance(self.name)

    @property
    def cluster_group_apps(self) -> ClusterGroupApps:
        # lazy loading, only generate the ClusterGroupApps object when someone tries to use it
        try:
            return self._cluster_group_apps
        except AttributeError:
            self._cluster_group_apps = ClusterGroupApps(
                self.config["clusterGroupApps"], self.layout
            )
            return self._cluster_group_apps

    @property
    def config(self) -> dict:
        # lazy loading, only try to load and process the configuration when something actually tries
        # to access it
        try:
            return self._config
        except AttributeError:
            result = {"clusters": {}, "clusterGroupApps": {}}
            files = Path(self.path).glob("**/*.yaml")
            for file in files:
                if os.path.basename(file) == "Chart.yaml":
                    continue
                if os.path.basename(os.path.dirname(file)) == "templates":
                    continue

                try:
                    with open(file, "r") as f:
                        try:
                            data = yaml.safe_load(f)
                        except yaml.YAMLError as exc:
                            print(
                                f"Failed to parse '{file}' as yaml: {exc}",
                                file=sys.stderr,
                            )
                            raise
                        result = deep_merge(result, data)
                except IOError as exc:
                    print(f"Failed to open '{file}': {exc}", file=sys.stderr)
                    raise
            self._config = result
            return self._config

    @property
    def clusters(self) -> dict:
        # lazy loading, only create the cluster objects when someone tries to access
        # the clusters
        try:
            return self._clusters
        except AttributeError:
            self._clusters = {}
            for cluster_config in self.config["clusters"]:
                cluster = Cluster(cluster_config, self.cluster_group_apps, self.layout)
                self._clusters[cluster.name] = cluster
            return self._clusters

    def select_clusters(self, regex: str) -> dict:
        """
        Given a regex to be matched against cluster names, the method returns a dictionary of
        clusters whose names match the regex.

        Parameters
        ----------
        regex: str
            a string that is treated as regex; it will be wrapped in ^$ before being compiled to
            a regex object; the method returns all clusters whose name match the resulting regex
        """
        # use an r"" string here the regex module interprets
        # potential \ characters instead of python
        selector = re.compile(r"^%s$" % regex)
        result = {}
        for name, cluster in self.clusters.items():
            match = selector.search(name)
            if match:
                result[name] = cluster
        return result


class GitCLI:
    """
    The GitCLI class is the interface to the git cli and wraps the actual execution of git commands.

    This is intended to be used for maintenance tasks like cleanups. For more complex tasks a git python
    module (for example GitPython) should be used.

    Attributes
    ----------
    git : str
        the git binary to use
    """

    def __init__(self, git: str = "git", debug: bool = False):
        self.git = git
        self.debug = debug

    def clean(self, params: list = ["-n"]) -> bool:
        """
        Executes git clean. Executes a dry-run if no parameters are provided.

        Parameters
        ----------
        params : list
            list of parameters to call git with
        """
        _, stderr, code = self._execute(["clean"] + params)
        if code != 0:
            print(stderr, file=sys.stderr)
            return False
        return True

    def clean_ignored(self) -> bool:
        """
        Performs a git clean that recursively deletes all files ignored by
        gitignores.
        """
        return self.clean(["-d", "-X", "-f"])

    def _execute(self, params: list) -> tuple:
        """
        Executes an arbitrary git command.

        Parameters
        ----------
        params : list
            list of parameters to call git with
        """
        base_cmd = [self.git]

        command = base_cmd + params
        if self.debug:
            print("Executing git command: %s" % " ".join(command), file=sys.stderr)

        command_result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout = ""
        stderr = ""
        try:
            if command_result.stdout:
                stdout = command_result.stdout.decode("UTF-8")
            if command_result.stderr:
                stderr = command_result.stderr.decode("UTF-8")
        except BrokenPipeError:
            # https://docs.python.org/3/library/signal.html#note-on-sigpipe
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            sys.exit(1)

        return stdout, stderr, command_result.returncode


class Helm:
    """
    The Helm class is the interface to helm and wraps the actual execution of the helm commands.

    Attributes
    ----------
    helm : str
        the helm binary to use
    debug : bool
        whether to execute the helm commands in debug mode (i.e. with --debug)
    """

    def __init__(self, helm: str = "helm", debug: bool = False):
        """
        Parameters
        ----------
        helm : str, optional
            the helm binary to use
        debug : bool, optional
            whether to execute the helm commands in debug mode (i.e. with --debug)
        """
        self.helm = helm
        self.debug = debug

    def template(
        self,
        release: str,
        namespace: str,
        chart: str,
        value_files: list = [],
        values: dict = {},
        show_only: list = [],
    ) -> tuple:
        """
        Executes "helm template" for the given chart.

        Parameters
        ----------
        release: str
            the release name to be used when rendering the application
        namespace: str
            the namespace to use when rendering the application
        chart : str
            the path to the helm chart that should be rendered
        value_files : list, optional
            list of path to value files that should be used when the chart is rendered
        values : dict, optional
            dict of values passed to helm template via --set or --set-string
            the dict follows the same semantics as the corresponding helm parameters, e.g. value keys
            must use dot notation to reference sub-keys (e.g. "key.subkey.subsubkey" ) and values
            must either be scalar or a list of scalars (i.e. you cannot pass a dict as a value);
            string values will be passed with --set-string, everything else will be passed with --set
        show_only : list, optional
            list of templates that should be rendered
        """
        command = ["template", release, chart, "-n", namespace]
        for f in value_files:
            command = command + ["-f", f]

        if show_only:
            for s in show_only:
                command = command + ["-s", os.path.join("templates", s)]

        # although technically we are passing all values as strings to
        # helm we need to tell helm if the value acutally IS a string.
        # E.g. should it treat "true" as boolean or as string?
        # passing --set flag=true treats it as boolean, but --set-string=true
        # treats it as string
        set_values = []
        set_string_values = []
        for key, value in values.items():
            item = f"{key}={value}"
            if isinstance(value, str):
                set_string_values.append(item)
                continue
            if isinstance(value, list):
                # lists are passed to helm on the command line as follows
                # --set "key={str,str,str,...}"
                # See https://helm.sh/docs/intro/using_helm/#the-format-and-limitations-of---set
                # So we need to convert the given list into the proper format, while considering
                # that join() only works on string-only lists and {} has syntactical meaning in f""
                # strings
                l = ",".join([str(i) for i in value])
                item = "%s={%s}" % (key, l)
            set_values.append(item)

        if set_values:
            command = command + ["--set", ",".join(set_values)]

        if set_string_values:
            command = command + ["--set-string", ",".join(set_string_values)]

        stdout, stderr, returncode = self._execute(command)
        if self._is_missing_dependency_err(stderr):
            stdout, stderr, returncode = self.dependency_build(chart)
            if returncode != 0:
                return stdout, stderr, returncode
            return self._execute(command)
        return stdout, stderr, returncode

    def dependency_build(self, chart: str) -> tuple:
        """
        Executes "helm dependency build" for the given chart.

        If successfull, this method creates a *.tgz for each not already
        fullfilled dependency in the charts/ directory of the chart and creates/updates
        the Chart.lock file in the directory of the chart.

        Parameters
        ----------
        chart : str
            the path to the helm chart for which the denpendencies should be pulled in
        """
        return self._execute(["dependency", "build", chart])

    # Taken straight from argocd:
    # https://github.com/argoproj/argo-cd/blob/a6c664b2aefc513936e9f56c1a373bdbddcd5727/util/helm/helm.go#L60
    def _is_missing_dependency_err(self, err: str) -> bool:
        """
        Checks if the given error is a missing dependency error.

        Parameters
        ----------
        err : str
            the error message to check
        """
        return ("found in requirements.yaml, but missing in charts" in err) or (
            "found in Chart.yaml, but missing in charts/ directory" in err
        )

    def _execute(self, params: list) -> tuple:
        """
        Executes an arbitrary helm command.

        Parameters
        ----------
        params : list
            list of parameters to call helm with
        """
        base_cmd = [self.helm]
        if self.debug:
            base_cmd = base_cmd + ["--debug"]

        command = base_cmd + params
        if self.debug:
            print("Executing helm command: %s" % " ".join(command), file=sys.stderr)

        command_result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout = ""
        stderr = ""
        try:
            if command_result.stdout:
                stdout = command_result.stdout.decode("UTF-8")
            if command_result.stderr:
                stderr = command_result.stderr.decode("UTF-8")
        except BrokenPipeError:
            # https://docs.python.org/3/library/signal.html#note-on-sigpipe
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            sys.exit(1)

        return stdout, stderr, command_result.returncode


def render(
    instance: Instance,
    cluster_regex: str = ".*",
    app_regex: str = ".*",
    fatal_errors: bool = False,
    helm_bin: str = "helm",
    git_bin: str = "git",
    git_clean: bool = True,
    debug: bool = False,
    show_only: list = [],
    full_results: bool = True,
    quiet: bool = False,
    warn_notfound: bool = False,
) -> int:
    """
    render() implements the "render" cli command. It uses the data in the
    provided instance (clusters, applications ...) to collect the relevant
    value files for each application and executes the proper helm calls to generate the
    Kubernetes resource yaml documents.

    Parametes
    ---------
    instance : Instance
        the Instance object for which the applications should be rendered
    cluster_regex : str, optional
        the regex used to select which clusters to operate on; the default '.*'
    app_regex : str, optional
        the regex used to select which applications on each cluster to operate on;
        the default is '.*'
    fatal_errors : bool, optional
        if working on multiple clusters / applications, fatal_errors controls whether
        a helm call that finishes with a with a non-zero exitcode stops the processing
        of further applications. The default is False, which means all applications on
        all clusters are processed, even when some of them fail to render.
    helm_bin : str, optional
        the helm binary to use; the default is 'helm'
    git_bin : str, optional
        the git binary to use; the default is 'git'
    git_clean : bool, optional
        whether to perform the git clean step before and after templating; the default is True
    debug : bool, optional
        whether to pass the --debug parameter to helm; the default is False
    show_only : list, optional
        list of filenames relative to the "template" directory of an application that
        should be rendered; if provided, only the template files provided in the parameter
        will be rendered for each application (using the -s helm parameter);
        the default is an empty list, meaning all templates are rendered
    full_results : bool, optional
        whether to show a list of exit codes for each application that has been rendered
        or only list the applications for which the render process finished with a non-zero
        exitcode; the default is False, only listing failed applications
    quiet : bool, optional
        if True, do not print the rendered yaml documents; can be used if you only want
        to check if everything is rendered properly, but do not care for the actual yaml documents;
        default is False
    warn_notfound : bool, optional
        if True, a missing application (i.e. an application that is listed in the configuration but does
        not exist in the filesystem) is not considered an error, meaning the function will still
        return a zero exit code even when an application is missing; nevertheless it will still
        list the application as failed in the execution results;
        the default is False, so missing applications result in a non-zero exitcode
    """
    clusters = instance.select_clusters(cluster_regex)
    helm = Helm(helm_bin, debug)

    if git_clean:
        git = GitCLI(git_bin, debug)
        git.clean_ignored()
        atexit.register(git.clean_ignored)

    exit_codes = {}
    for clustername, cluster in clusters.items():
        applications = cluster.select_applications(app_regex)
        for appname, app in applications.items():
            print(
                f"################ {clustername} {appname} ################",
                file=sys.stderr,
            )
            if not app.exists:
                print(
                    f"Application '{appname}' not found in path '{app.path}'!",
                    file=sys.stderr,
                )
                # trying to render a non existing app would cause a helm error
                # so we can use the fatal-errors flag here to decide if we
                # should continue (without calling helm, making this situation
                # a warning) or if we should treat it as an error and bail out.
                if fatal_errors:
                    return 99
                exit_codes[f"{clustername} {appname}"] = 99
                continue

            value_paths = []
            value_paths.append(app.values_path)
            value_paths.append(app.secrets_path)
            value_paths.append(app.addon_values_path)
            value_paths.append(app.addon_secrets_path)
            value_paths.extend(cluster.app_group_values_file_paths(appname))
            value_paths.extend(cluster.app_cluster_values_file_paths(appname))
            value_paths = list(filter(None, value_paths))

            # pass argocd metadata as explicit values to helm
            #
            # the template rendering the ArgoCD application resource
            # adds the same values as parameters to each app when
            # rendering the resource
            values = {
                "argocdParams.clusterName": clustername,
                "argocdParams.clusterAPI": cluster.api,
                "argocdParams.argocdStage": instance.name,
            }

            stdout, stderr, returncode = helm.template(
                f"{app.name}-{clustername}",
                app.namespace,
                app.path,
                value_paths,
                values,
                show_only,
            )

            if stdout and not quiet:
                print(stdout)
            if stderr:
                print(stderr, file=sys.stderr)

            if fatal_errors and (returncode != 0):
                return returncode
            exit_codes[f"{clustername} {appname}"] = returncode

    exit_code = 0
    executions = list(exit_codes.keys())

    # no chart was rendered (because the cluster/app regex did not match anything)
    # the execution was successfull, so we can return the default exit code
    if len(executions) == 0:
        return exit_code

    # exactly one chart has been rendered, so we return the exit code of this
    # helm call
    if len(executions) == 1:
        return exit_codes[executions[0]]

    # more than one chart has been rendered, so we return an overview of
    # all exit codes
    print("Execution results:", file=sys.stderr)
    for exec in executions:
        code = exit_codes[exec]

        if (code != 0) or full_results:
            print(f"  {exec}: {code}", file=sys.stderr)
        if code != 0:
            # 99 is a "virtual" exit code, assigned when an application exists in the config
            # but not in the filesystem
            if code == 99 and warn_notfound:
                continue
            exit_code = 1
    if exit_code == 0:
        print("  All applications rendered successfully!", file=sys.stderr)
    return exit_code


def list_clusters(instance: Instance, cluster_regex: str = ".*") -> int:
    """
    list_clusters() implements the "list_cluster" cli command. It prints a list
    of clusters matching the provided regex.

    Parameters
    ----------
    instance : Instance
        the Instance object for which the clusters should be listed
    cluster_regex : str, optional
        the regex used to select which clusters to operate on; the default '.*'
    """
    clusters = instance.select_clusters(cluster_regex)

    for name in clusters.keys():
        print(name)

    return 0


def list_cluster_apps(
    instance: Instance,
    cluster_regex: str = ".*",
    app_regex: str = ".*",
    paths: bool = False,
) -> int:
    """
    list_cluster_apps() implements the "list_cluster_apps" cli command. For each
    cluster matching the given cluster regex, it prints a list of all applications
    assigned to the cluster that match the provided application regex.

    It can optionally also show the path to the application directory and the paths
    to the different value files of the application (app values, cluster values, group values...)

    Parameters
    ----------
    instance : Instance
        the Instance object for which the cluster applications should be listed
    cluster_regex : str, optional
        the regex used to select which clusters to operate on; the default '.*'
    app_regex : str, optional
        the regex used to select which applications on each cluster to operate on;
        the default is '.*'
    paths: bool, optional
        whether to print the application and value paths for each application;
        default is False
    """
    clusters = instance.select_clusters(cluster_regex)
    for clustername, cluster in clusters.items():
        indent = ""
        if len(clusters) > 1:
            print(f"{clustername}:")
            indent = "  "
        applications = cluster.select_applications(app_regex)
        for appname, app in applications.items():
            result = f"{indent}{appname}"
            if paths:
                result = f"{result} ({app.path})"
                value_paths = []
                value_paths.append(app.values_path)
                value_paths.append(app.secrets_path)
                value_paths.append(app.addon_values_path)
                value_paths.append(app.addon_secrets_path)
                value_paths.extend(cluster.app_group_values_file_paths(appname))
                value_paths.extend(cluster.app_cluster_values_file_paths(appname))
                value_paths = list(filter(None, value_paths))

                result = "%s\n    %s" % (result, "\n    ".join(value_paths))
            print(result)

    return 0


if __name__ == "__main__":

    def cmd_render(args: argparse.Namespace, instance: Instance) -> int:
        return render(
            instance,
            args.clusters,
            args.applications,
            args.fatal_errors,
            args.helm,
            args.git,
            not args.no_git_clean,
            args.debug,
            args.show_only,
            args.full_execution_results,
            args.quiet,
            args.warn_notfound,
        )

    def cmd_list_clusters(args: argparse.Namespace, instance: Instance) -> int:
        return list_clusters(instance, args.clusters)

    def cmd_list_cluster_apps(args: argparse.Namespace, instance: Instance) -> int:
        return list_cluster_apps(instance, args.clusters, args.applications, args.paths)

    parser = argparse.ArgumentParser(
        # using 'description=__doc__' here kills all formatting of the header comment, making
        # it pretty much unreadable.
        description="Render argocd applications for clusters."
    )
    parser.add_argument("--root", default=".", help="root directory")
    parser.add_argument(
        "--instance-dir",
        default="instances",
        help="instance root directory",
    )
    parser.add_argument(
        "--projects-dir",
        default="projects",
        help="projects root directory",
    )
    parser.add_argument(
        "--project-apps-dir",
        default="applications",
        help="directory for project applications",
    )
    parser.add_argument(
        "--project-values-dir",
        default="values",
        help="directory for project values",
    )
    parser.add_argument(
        "--cluster-values-dir",
        default="clusters",
        help="directory for cluster values, below values dir",
    )
    parser.add_argument(
        "--group-values-dir",
        default="groups",
        help="directory for group values, below values dir",
    )
    parser.add_argument(
        "--shared-charts-dir",
        default="shared/charts",
        help="directory for shared charts",
    )
    parser.add_argument(
        "--instance",
        default="int",
        help="name of the argocd instance",
    )

    subparsers = parser.add_subparsers(dest="cmd")
    render_parser = subparsers.add_parser(
        "render", help="render application for cluster"
    )
    render_parser.add_argument(
        "clusters",
        metavar="clusters",
        nargs="?",
        default=".*",
        help="the clusters for which to render the applications; ^$ wrapped regex",
    )
    render_parser.add_argument(
        "applications",
        metavar="apps",
        nargs="?",
        default=".*",
        help="applications to render; ^$ wrapped regex",
    )
    render_parser.add_argument(
        "--helm", metavar="file", default="helm", help="helm binary to use"
    )
    render_parser.add_argument(
        "--git", metavar="file", default="git", help="git binary to use"
    )
    render_parser.add_argument(
        "--no-git-clean",
        default=False,
        action="store_true",
        help="do not perform git cleanup before and after templating",
    )
    render_parser.add_argument(
        "-x",
        "--full-execution-results",
        default=False,
        action="store_true",
        help="Show all apps in the execution results instead of just failed ones",
    )
    render_parser.add_argument(
        "--fatal-errors",
        default=False,
        action="store_true",
        help="exit on first helm error",
    )
    render_parser.add_argument(
        "--warn-notfound",
        default=False,
        action="store_true",
        help="only warn if the application was not found",
    )
    render_parser.add_argument(
        "-s",
        "--show-only",
        metavar="file.yaml",
        action="append",
        help="yaml file name of the template to be rendered (can be used multiple times)",
    )
    render_parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="print helm command and call helm with --debug",
    )
    render_parser.add_argument(
        "--quiet",
        default=False,
        action="store_true",
        help="do not print the rendered yaml documents",
    )
    render_parser.set_defaults(func=cmd_render)

    list_clusters_parser = subparsers.add_parser("list_clusters", help="list clusters")
    list_clusters_parser.add_argument(
        "clusters",
        metavar="clusters",
        nargs="?",
        default=".*",
        help="the clusters for which to list the applications; ^$ wrapped regex",
    )
    list_clusters_parser.set_defaults(func=cmd_list_clusters)

    list_cluster_apps_parser = subparsers.add_parser(
        "list_cluster_apps", help="list apps for a cluster"
    )
    list_cluster_apps_parser.add_argument(
        "clusters",
        metavar="clusters",
        nargs="?",
        default=".*",
        help="the clusters for which to list the applications; ^$ wrapped regex",
    )
    list_cluster_apps_parser.add_argument(
        "applications",
        metavar="apps",
        nargs="?",
        default=".*",
        help="only list certain applications; ^$ wrapped regex",
    )
    list_cluster_apps_parser.add_argument(
        "--paths", default=False, action="store_true", help="show app paths"
    )
    list_cluster_apps_parser.set_defaults(func=cmd_list_cluster_apps)

    args = parser.parse_args()
    layout = DirectoryLayout(
        args.root,
        args.instance_dir,
        args.projects_dir,
        args.project_apps_dir,
        args.project_values_dir,
        args.cluster_values_dir,
        args.group_values_dir,
        args.shared_charts_dir,
    )
    try:
        instance = Instance(args.instance, layout)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args, instance))
