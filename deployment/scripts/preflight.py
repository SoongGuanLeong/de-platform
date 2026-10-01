#!/usr/bin/env python3
"""The preflight (docs/local-development.md section 5).

The run refuses rather than degrades. It answers four questions before a single
container starts:

1. Can this host hold the profile at all? MemAvailable must clear the profile's
   declared peak plus the 512 MiB reserve. Below that the run refuses and names
   the shortfall in MiB; it does not start the services it can and hope.
2. If it cannot hold the full profile but can hold the reduced variant, it says
   so and names the reduced peak rather than starting a run that will thrash.
   The reduced variant is offered, never applied silently, because its evidence
   item has to be labelled as reduced.
3. Is the pinned toolchain the one the bring-up was executed against?
4. Is the host able to enforce what the compose files declare - cgroups v2, a
   delegated cpu controller, free ports, and a runtime/secrets whose files exist
   at mode 0600? The ownership remap is applied by
   deployment/scripts/fix-secret-ownership.sh before this runs, and the remap
   itself is not asserted here: what is asserted is the precondition the
   container needs, that the file exists and is not group- or world-readable.

Every check is a refusal, and a refusal exits non-zero, so the documented smoke
command cannot proceed past a host that cannot hold the run.

Run: deployment/scripts/preflight.sh <profile> [--reduced]
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import stat
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTER = os.path.join(ROOT, "deployment", "budgets", "profiles.yaml")
TOOLS_LOCK = os.path.join(ROOT, "deployment", "tools.lock")
COMPOSE_DIR = os.path.join(ROOT, "deployment", "compose")

EXIT_OK = 0
EXIT_REFUSE = 1
EXIT_OFFER_REDUCED = 3

problems: list[str] = []


def say(message: str) -> None:
    print(message)


def problem(message: str) -> None:
    problems.append(message)


def load_lock() -> dict:
    values: dict = {}
    with open(TOOLS_LOCK, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            raw = raw.strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
                raw = raw[1:-1]
            values[key.strip()] = raw
    return values


def version_tuple(text: str):
    numbers = re.findall(r"[0-9]+", text)
    return tuple(int(n) for n in numbers[:4]) or (0,)


def mem_available_mib() -> int:
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    raise SystemExit("preflight: /proc/meminfo has no MemAvailable")


def compose_file(profile: str) -> str:
    path = os.path.join(COMPOSE_DIR, profile + ".yml")
    if not os.path.exists(path):
        raise SystemExit("preflight: no compose file for profile " + profile)
    return path


def check_host_memory(profile: str, document: dict, reduced: bool) -> int:
    entry = document["profiles"][profile]
    reserve = document["anchor"]["reserve_mib"]
    variant = entry.get("reduced_variant")
    if reduced and not isinstance(variant, dict):
        raise SystemExit("preflight: profile " + profile + " declares no reduced variant")
    if entry.get("declared_per_run"):
        # The benchmark profile declares no peak of its own: each run declares
        # its ceiling in its protocol (completion bar section 8). What the host
        # has to hold is the largest peak the profile's rule permits.
        peak = entry["rule"]["max_peak_memory_mib"]
        label = "largest permitted peak"
    elif reduced:
        peak = variant["peak"]["memory_mib"]
        label = "reduced peak"
    else:
        peak = entry["peak"]["memory_mib"]
        label = "peak"
    required = peak + reserve
    available = mem_available_mib()
    say(
        "host: MemAvailable "
        + str(available)
        + " MiB, reserve "
        + str(reserve)
        + " MiB, "
        + profile
        + " "
        + label
        + " "
        + str(peak)
        + " MiB, required "
        + str(required)
        + " MiB"
    )
    if available >= required:
        return EXIT_OK
    if (
        not reduced
        and isinstance(variant, dict)
        and available >= variant["peak"]["memory_mib"] + reserve
    ):
        say(
            "preflight: REFUSED the full run. It needs "
            + str(required)
            + " MiB and the host has "
            + str(available)
            + " MiB, a shortfall of "
            + str(required - available)
            + " MiB."
        )
        say(
            "preflight: the reduced variant needs "
            + str(variant["peak"]["memory_mib"] + reserve)
            + " MiB and fits. Re-run with --reduced to accept it; its evidence item is then"
            " labelled as reduced, and " + str(variant.get("consequence", "")).strip()
        )
        return EXIT_OFFER_REDUCED
    say(
        "preflight: REFUSED. "
        + profile
        + " needs "
        + str(required)
        + " MiB and the host has "
        + str(available)
        + " MiB, a shortfall of "
        + str(required - available)
        + " MiB."
    )
    return EXIT_REFUSE


def check_toolchain(lock: dict) -> None:
    try:
        client = subprocess.run(
            ["podman", "version", "--format", "{{.Client.Version}}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        problem("podman is not runnable: " + str(error))
        return
    floor = lock.get("PODMAN_MIN_VERSION", "0")
    say("podman: " + client + " (floor " + floor + ")")
    if version_tuple(client) < version_tuple(floor):
        problem("podman " + client + " is below the declared floor " + floor)

    try:
        compose = subprocess.run(
            ["podman-compose", "--version"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        problem("podman-compose is not runnable: " + str(error))
        return
    # podman-compose --version prints its own line and the podman version line, in
    # an order that depends on how the streams are captured, so the pattern names
    # the tool rather than taking the first version-looking token.
    match = re.search(r"podman-compose version ([0-9][0-9.]*)", compose)
    found = match.group(1) if match else "0"
    floor = lock.get("PODMAN_COMPOSE_MIN_VERSION", "0")
    say("podman-compose: " + found + " (floor " + floor + ")")
    if version_tuple(found) < version_tuple(floor):
        problem("podman-compose " + found + " is below the declared floor " + floor)


def check_cgroups() -> None:
    try:
        with open("/proc/self/mountinfo", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        problem("cannot read /proc/self/mountinfo: " + str(error))
        return
    if "cgroup2" not in text:
        problem(
            "cgroups v2 is not mounted; podman documents --memory and --cpus as unsupported on"
            " cgroups v1 rootless"
        )
        return
    say("cgroups: v2")
    controllers_path = "/sys/fs/cgroup/cgroup.controllers"
    if os.path.exists(controllers_path):
        with open(controllers_path, encoding="utf-8") as handle:
            controllers = handle.read().split()
        say("cgroup controllers: " + " ".join(controllers))
        if "cpu" not in controllers:
            problem(
                "the cpu cgroup controller is not available, so"
                " deploy.resources.limits.cpus cannot be enforced. The documented fix is"
                " Delegate=memory pids cpu cpuset at"
                " /etc/systemd/system/user@.service.d/delegate.conf plus a re-login"
            )
    else:
        problem("cannot read /sys/fs/cgroup/cgroup.controllers")


def check_ports(compose_path: str) -> None:
    with open(compose_path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    seen = []
    for name, service in (document.get("services") or {}).items():
        for entry in service.get("ports") or []:
            parts = str(entry).split(":")
            if len(parts) < 2:
                problem(compose_path + ": port " + str(entry) + " has no host port")
                continue
            host_port = int(parts[-2])
            seen.append((host_port, name))
    for host_port, name in sorted(seen):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", host_port))
            except OSError:
                problem(
                    "port "
                    + str(host_port)
                    + " ("
                    + name
                    + ") is already bound; a bind failure mid-bring-up "
                    "leaves a half-started profile"
                )
    say("ports: " + str(len(seen)) + " checked, " + str(len(problems)) + " problem(s) so far")


def check_secrets(compose_path: str) -> None:
    with open(compose_path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    required = []
    for service in (document.get("services") or {}).values():
        for mount in service.get("volumes") or []:
            text = str(mount)
            if "/run/secrets/" not in text:
                continue
            source = text.split(":")[0]
            if source.startswith("../../runtime/secrets/"):
                required.append((os.path.basename(source), source))
    if not required:
        say("secrets: none mounted by this profile")
        return
    for name, source in sorted(set(required)):
        path = os.path.normpath(os.path.join(os.path.dirname(compose_path), source))
        if not os.path.exists(path):
            problem(
                "secret "
                + name
                + " is missing at "
                + os.path.relpath(path, ROOT)
                + "; run deployment/scripts/generate-secrets.sh"
            )
            continue
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode & 0o077:
            problem(
                "secret "
                + name
                + " is mode "
                + oct(mode)
                + "; a secret is a read-only file (ADR-0028)"
            )
    say("secrets: " + str(len(set(required))) + " mounted by this profile")


def main() -> int:
    parser = argparse.ArgumentParser(description="the profile preflight")
    parser.add_argument(
        "profile", choices=["smoke", "batch", "streaming", "observability", "benchmark"]
    )
    parser.add_argument(
        "--reduced",
        action="store_true",
        help="accept the profile's reduced variant and label the run as reduced",
    )
    args = parser.parse_args()

    with open(REGISTER, encoding="utf-8") as handle:
        register = yaml.safe_load(handle)
    lock = load_lock()

    status = check_host_memory(args.profile, register, args.reduced)
    if status != EXIT_OK:
        return status

    check_toolchain(lock)
    check_cgroups()
    compose_path = compose_file(args.profile)
    check_ports(compose_path)
    check_secrets(compose_path)

    if problems:
        for message in problems:
            print("preflight: " + message, file=sys.stderr)
        return EXIT_REFUSE
    say("preflight: " + args.profile + (", reduced" if args.reduced else "") + " may run")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
