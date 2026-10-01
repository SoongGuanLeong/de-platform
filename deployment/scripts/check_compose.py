#!/usr/bin/env python3
"""The compose-subset lint (docs/completion-bar.md sections 11 and 12).

Six things are asserted, all of them from the artefacts rather than from prose:

1. Every compose file under deployment/compose/ uses only the portable runtime
   subset, and deploy is permitted only at resources.limits.{cpus,memory,pids}.
2. Every declared limit resolves against the ceiling register in
   deployment/budgets/profiles.yaml, exactly - a limit that matches no ceiling
   and no declared override fails.
3. Every profile peak in that register is recomputed from its ceilings, so a
   peak that does not match its parts fails, and the benchmark profile is
   checked against its declared rule instead.
4. Every image is pinned by digest and the reference is the one
   deployment/tools.lock holds, so the pin registry and the compose set cannot
   drift apart. The images the platform builds are asserted to be the declared
   ones rather than silently unpinned.
5. Every JVM service declares the JDK its image carries, the declaration is one
   docs/research/03-longevity-audit.md accepts, and it agrees with the image tag
   where the tag names one. Every ClickHouse profile's mounted memory XML
   declares the register's ceiling and does not clamp it with the image's
   default ratio.
6. Every compose service is classified in exactly one runtime list in
   deployment/tools.lock, so a service that no list names fails rather than
   silently carrying no runtime assertion.

Run: deployment/scripts/check-compose.sh
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

import yaml

# --root points the lint at a throwaway copy of deployment/, which is how
# deployment/scripts/test-check-compose.sh proves the checks are load-bearing:
# each mutation must fail against a tree that is not the working one.
if "--root" in sys.argv:
    ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1])
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPOSE_DIR = os.path.join(ROOT, "deployment", "compose")
REGISTER = os.path.join(ROOT, "deployment", "budgets", "profiles.yaml")
TOOLS_LOCK = os.path.join(ROOT, "deployment", "tools.lock")
IMAGES_DIR = os.path.join(ROOT, "deployment", "images")

# The portable runtime subset. docs/completion-bar.md section 11 names the
# runtime-affecting keys; command and entrypoint are added because a service
# whose role is chosen by its command (Flink's jobmanager and taskmanager) has
# no other way to declare it, and both named providers implement them
# identically. The addition is recorded in the register's limitations.
TOP_LEVEL_KEYS = {"name", "services", "volumes", "networks"}
SERVICE_KEYS = {
    "image",
    "restart",
    "command",
    "entrypoint",
    "environment",
    "env_file",
    "ports",
    "volumes",
    "networks",
    "healthcheck",
    "profiles",
    "extra_hosts",
    "depends_on",
    "deploy",
}
DEPLOY_KEYS = {"resources"}
RESOURCES_KEYS = {"limits"}
LIMIT_KEYS = {"cpus", "memory", "pids"}
HEALTHCHECK_KEYS = {"test", "interval", "timeout", "retries", "start_period", "disable"}

# The register's service keys and the tools.lock variable each one's image is
# pinned in. A service absent from this map is a lint failure, so adding a
# service to a profile means adding its pin.
IMAGE_VAR = {
    "postgres": "IMAGE_postgres",
    "seaweedfs": "IMAGE_seaweedfs",
    "polaris": "IMAGE_polaris",
    "clickhouse": "IMAGE_clickhouse",
    "kafka": "IMAGE_kafka",
    "debezium-connect": "IMAGE_debezium_connect",
    "flink-jobmanager": "IMAGE_flink",
    "flink-taskmanager": "IMAGE_flink",
    "flink-client": "IMAGE_flink",
    "spark": "IMAGE_spark",
    "prometheus": "IMAGE_prometheus",
    "grafana": "IMAGE_grafana",
    "alertmanager": "IMAGE_alertmanager",
}

# The JDKs docs/research/03-longevity-audit.md accepts. Anything else - 25 and 26
# in particular - is rejected there, and a declaration outside this set is a lint
# failure rather than a silent drift.
ACCEPTED_JDK = ("17", "21")

PROFILE_OF_PROJECT = {
    "de-platform-smoke": "smoke",
    "de-platform-batch": "batch",
    "de-platform-streaming": "streaming",
    "de-platform-observability": "observability",
    "de-platform-benchmark": "benchmark",
}

failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def load_tools_lock() -> dict:
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


def parse_memory_mib(value) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([bkmgBKMG]?)", text)
    if not match:
        raise ValueError("unparseable memory value " + repr(value))
    number = float(match.group(1))
    unit = match.group(2).lower()
    factor = {"": 1, "b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[unit]
    return int(number * factor / (1024**2))


def check_subset(path: str, document: dict) -> None:
    for key in document:
        if key not in TOP_LEVEL_KEYS:
            fail(path + ": top-level key " + repr(key) + " is outside the portable subset")
    for name, service in (document.get("services") or {}).items():
        where = path + ": service " + name
        if not isinstance(service, dict):
            fail(where + " is not a mapping")
            continue
        for key in service:
            if key not in SERVICE_KEYS:
                fail(where + ": key " + repr(key) + " is outside the portable subset")
        if "depends_on" in service and isinstance(service["depends_on"], dict):
            fail(
                where
                + ": depends_on uses the long form; only the list form without condition ports"
            )
        healthcheck = service.get("healthcheck")
        if isinstance(healthcheck, dict):
            for key in healthcheck:
                if key not in HEALTHCHECK_KEYS:
                    fail(
                        where + ": healthcheck key " + repr(key) + " is outside the portable subset"
                    )
        deploy = service.get("deploy")
        if deploy is None:
            continue
        for key in deploy:
            if key not in DEPLOY_KEYS:
                fail(where + ": deploy key " + repr(key) + " is outside deploy.resources")
        resources = deploy.get("resources") or {}
        for key in resources:
            if key not in RESOURCES_KEYS:
                fail(where + ": deploy.resources key " + repr(key) + " is not limits")
        limits = resources.get("limits") or {}
        for key in limits:
            if key not in LIMIT_KEYS:
                fail(where + ": deploy.resources.limits key " + repr(key) + " is not permitted")


def ceiling_for(register: dict, profile: str, service: str):
    profiles = register["profiles"]
    if profile == "benchmark":
        worked = profiles["benchmark"]["worked_example"]["services"]
        if service in worked:
            entry = worked[service]
            return entry["memory_mib"], float(entry["cpus"])
        return None
    overrides = (profiles[profile] or {}).get("overrides") or {}
    if service in overrides:
        entry = overrides[service]
        return entry["memory_mib"], float(entry["cpus"])
    ceilings = register["ceilings"]
    if service in ceilings:
        entry = ceilings[service]
        return entry["memory_mib"], float(entry["cpus"])
    return None


def check_limits(path: str, profile: str, document: dict, register: dict) -> None:
    for name, service in (document.get("services") or {}).items():
        limits = (((service.get("deploy") or {}).get("resources") or {}).get("limits")) or {}
        if not limits:
            fail(path + ": service " + name + " declares no deploy.resources.limits")
            continue
        declared = ceiling_for(register, profile, name)
        if declared is None:
            fail(path + ": service " + name + " has no ceiling in the register for " + profile)
            continue
        if "memory" not in limits or "cpus" not in limits:
            fail(path + ": service " + name + " must declare both memory and cpus")
            continue
        want_mem, want_cpus = declared
        got_mem = parse_memory_mib(limits["memory"])
        got_cpus = float(limits["cpus"])
        if got_mem != want_mem:
            fail(
                path
                + ": service "
                + name
                + " memory is "
                + str(got_mem)
                + " MiB, register says "
                + str(want_mem)
            )
        if abs(got_cpus - want_cpus) > 1e-9:
            fail(
                path
                + ": service "
                + name
                + " cpus is "
                + str(got_cpus)
                + ", register says "
                + str(want_cpus)
            )


def check_clickhouse_limits(
    relative: str, path: str, profile: str, document: dict, register: dict
) -> None:
    """The mounted ClickHouse memory XML must declare the register's ceiling.

    ClickHouse takes the smaller of max_server_memory_usage and
    max_server_memory_usage_to_ram_ratio times the container's cgroup limit. At
    the image's default ratio of 0.9 the declared ceiling is clamped to 90% of
    it, so the ceiling the register declares is not the ceiling the server
    enforces: on 2026-10-01 a declared 872415232 was enforced as 785173708. Both
    keys are asserted, and the ratio is the half that was missing.
    """
    directory = os.path.dirname(path)
    for name, service in (document.get("services") or {}).items():
        if name != "clickhouse":
            continue
        ceiling = ceiling_for(register, profile, name)
        if ceiling is None:
            continue
        for mount in service.get("volumes") or []:
            text = str(mount)
            if "/etc/clickhouse-server/config.d/limits.xml" not in text:
                continue
            source = os.path.join(directory, text.split(":")[0])
            if not os.path.exists(source):
                fail(
                    relative
                    + ": clickhouse mounts "
                    + text.split(":")[0]
                    + ", which does not exist"
                )
                continue
            with open(source, encoding="utf-8") as handle:
                xml = handle.read()
            declared = re.search(
                r"<max_server_memory_usage>([0-9]+)</max_server_memory_usage>", xml
            )
            want = ceiling[0] * 1024 * 1024
            if declared is None:
                fail(source + ": no max_server_memory_usage element")
            elif int(declared.group(1)) != want:
                fail(
                    source
                    + ": max_server_memory_usage is "
                    + declared.group(1)
                    + ", register says "
                    + str(want)
                )
            ratio = re.search(
                r"<max_server_memory_usage_to_ram_ratio>([0-9.]+)</max_server_memory_usage_to_ram_ratio>",
                xml,
            )
            if ratio is None:
                fail(
                    source
                    + ": no max_server_memory_usage_to_ram_ratio element, so the image"
                    + " default of 0.9 clamps the declared ceiling"
                )
            elif float(ratio.group(1)) < 1.0:
                fail(
                    source
                    + ": max_server_memory_usage_to_ram_ratio is "
                    + ratio.group(1)
                    + ", which clamps the declared ceiling below the register's"
                )


def check_images(path: str, document: dict, lock: dict) -> None:
    built = set(lock.get("UNPINNED_BUILT_SERVICES", "").split())
    for name, service in (document.get("services") or {}).items():
        image = service.get("image")
        if not image:
            fail(path + ": service " + name + " declares no image")
            continue
        if name in built:
            if not image.startswith("localhost/de-platform/"):
                fail(
                    path
                    + ": built service "
                    + name
                    + " must reference localhost/de-platform/, not "
                    + image
                )
            continue
        variable = IMAGE_VAR.get(name)
        if variable is None:
            fail(path + ": service " + name + " has no entry in the lint's image map")
            continue
        if "@sha256:" not in image:
            fail(path + ": service " + name + " image is not pinned by digest: " + image)
        if lock.get(variable) != image:
            fail(
                path
                + ": service "
                + name
                + " image "
                + image
                + " != tools.lock "
                + variable
                + "="
                + str(lock.get(variable))
            )


def check_shared_service_bodies(files: list) -> None:
    """A service body is the same in every profile that runs it.

    The five compose files are self-contained rather than overlays, so a service
    body is written more than once. A limit that drifts is caught by
    check_limits and an image reference that drifts by check_images, but an
    environment, port, healthcheck or command that drifts in one copy only is
    invisible to both. This compares the copies. The deploy block is excluded
    because the ceiling is what differs by profile, and the ClickHouse
    limits-*.xml mount is excluded because the file it names is the profile's
    ceiling written in another form.
    """
    seen: dict = {}
    for path in files:
        relative = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        for name, service in (document.get("services") or {}).items():
            body = {key: value for key, value in service.items() if key != "deploy"}
            body["volumes"] = [
                mount
                for mount in body.get("volumes") or []
                if "/etc/clickhouse-server/config.d/limits.xml" not in str(mount)
            ]
            rendered = json.dumps(body, sort_keys=True)
            previous = seen.setdefault(name, (rendered, relative))
            if previous[0] != rendered:
                fail(
                    "service "
                    + name
                    + " differs between "
                    + previous[1]
                    + " and "
                    + relative
                    + ", and only its deploy block and its ClickHouse ceiling mount may differ"
                )


def check_service_classification(files: list, lock: dict) -> None:
    """Every compose service is classified in exactly one runtime list.

    check_runtime_versions iterates those lists, so a service in none of them
    would silently carry no runtime assertion. This makes the omission a failure
    rather than an absence, which is the difference between a rule and a list
    someone has to remember to extend.
    """
    lists = {
        "JVM_SERVICES": set(lock.get("JVM_SERVICES", "").split()),
        "PYTHON_SERVICES": set(lock.get("PYTHON_SERVICES", "").split()),
        "NATIVE_SERVICES": set(lock.get("NATIVE_SERVICES", "").split()),
        "UNPINNED_BUILT_SERVICES": set(lock.get("UNPINNED_BUILT_SERVICES", "").split()),
    }
    seen: set = set()
    for path in files:
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        seen.update((document.get("services") or {}).keys())
    for name in sorted(seen):
        members = [key for key, values in lists.items() if name in values]
        if not members:
            fail(
                "service "
                + name
                + " is in no runtime list in deployment/tools.lock: add it to JVM_SERVICES, "
                "PYTHON_SERVICES, NATIVE_SERVICES or UNPINNED_BUILT_SERVICES"
            )
        elif len(members) > 1:
            fail("service " + name + " is in more than one runtime list: " + ", ".join(members))
    for key, values in lists.items():
        for name in sorted(values - seen):
            fail(key + " names " + name + ", which no compose file declares")


def check_image_runtimes(lock: dict) -> None:
    # The JDK each JVM image carries, each Python image's interpreter version,
    # and each Dockerfile's base. The JDK is asserted as a declaration rather
    # than as "17 everywhere". Research 03 recommended pinning every JVM image to JDK 17,
    # but three of the pinned upstream images ship JDK 21 and publish no JDK-17
    # variant, so the platform asserts the measured runtime per image and that
    # every declared value is one the research accepts. The reason is recorded in
    # deployment/tools.lock beside the declarations.
    declared: dict = {}
    for service in lock.get("JVM_SERVICES", "").split():
        variable = IMAGE_VAR.get(service)
        if variable is None:
            fail("JVM_SERVICES names " + service + ", which the lint's image map does not know")
            continue
        key = "JVM_JDK_" + service.replace("-", "_")
        jdk = lock.get(key)
        if not jdk:
            fail("service " + service + " runs a JVM image but declares no JDK (" + key + ")")
            continue
        if jdk not in ACCEPTED_JDK:
            fail(
                "service "
                + service
                + " declares JDK "
                + jdk
                + ", and only "
                + " and ".join(ACCEPTED_JDK)
                + " are accepted (docs/research/03-longevity-audit.md)"
            )
        image = lock.get(variable, "")
        tagged = re.search(r"-java([0-9]+)", image)
        if tagged and tagged.group(1) != jdk:
            fail(
                "service "
                + service
                + " declares JDK "
                + jdk
                + " but its image tag says java"
                + tagged.group(1)
                + ": "
                + image
            )
        first = declared.setdefault(variable, (jdk, service))
        if first[0] != jdk:
            fail(
                "services "
                + first[1]
                + " and "
                + service
                + " share "
                + variable
                + " but declare JDK "
                + first[0]
                + " and "
                + jdk
            )
    for service in lock.get("PYTHON_SERVICES", "").split():
        variable = IMAGE_VAR.get(service)
        if variable is None:
            fail("PYTHON_SERVICES names " + service + ", which the lint's image map does not know")
            continue
        image = lock.get(variable, "")
        if "python:3.12" not in image:
            fail("Python image for " + service + " is not python:3.12: " + image)
    for path in sorted(glob.glob(os.path.join(IMAGES_DIR, "**", "Dockerfile*"), recursive=True)):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for match in re.finditer(r"^FROM\s+(\S+)", text, re.MULTILINE):
            base = match.group(1)
            if "python" in base and "python:3.12" not in base:
                fail(path + ": Python base is not 3.12: " + base)
            if "temurin" in base or "jdk" in base or "openjdk" in base:
                has_version = any(
                    ":" + version in base or "-" + version in base for version in ACCEPTED_JDK
                )
                if not has_version:
                    fail(path + ": JVM base is not 17 or 21: " + base)


def check_peaks(register: dict) -> None:
    ceilings = register["ceilings"]

    def entry(profile: str, service: str):
        overrides = (register["profiles"][profile] or {}).get("overrides") or {}
        if service in overrides:
            value = overrides[service]
            return value["memory_mib"], float(value["cpus"])
        value = ceilings[service]
        return value["memory_mib"], float(value["cpus"])

    def total(profile: str, services):
        memory = 0
        cpus = 0.0
        for service in services:
            m, c = entry(profile, service)
            memory += m
            cpus += c
        return memory, cpus

    for name, profile in register["profiles"].items():
        # preflight.py resolves a profile's requirement from peak, or from
        # rule.max_peak_memory_mib when the profile declares its ceiling per run.
        # A profile with neither crashed the preflight for that profile on
        # 2026-10-01, so the shape it depends on is asserted here.
        if not profile.get("peak") and not (
            profile.get("declared_per_run")
            and (profile.get("rule") or {}).get("max_peak_memory_mib")
        ):
            fail(
                "register: profile "
                + name
                + " declares neither peak nor a per-run rule the preflight can resolve"
            )
            continue
        if name == "benchmark":
            worked = profile["worked_example"]["services"]
            peak = profile["worked_example"]["peak"]
            want_mem = sum(v["memory_mib"] for v in worked.values())
            want_cpus = sum(float(v["cpus"]) for v in worked.values())
            if (peak["memory_mib"], float(peak["cpus"])) != (want_mem, round(want_cpus, 6)):
                fail("register: benchmark worked example peak does not match its parts")
            rule = profile["rule"]
            if peak["memory_mib"] > rule["max_peak_memory_mib"] or float(peak["cpus"]) > float(
                rule["max_peak_cpus"]
            ):
                fail("register: benchmark worked example exceeds the declared rule")
            continue
        if name == "smoke":
            single = ceilings[profile["single_service_ceiling"]]
            want = (single["memory_mib"], float(single["cpus"]))
            got = (profile["peak"]["memory_mib"], float(profile["peak"]["cpus"]))
            if got != want:
                fail("register: smoke peak " + str(got) + " is not the single ceiling " + str(want))
            continue
        resident_mem, resident_cpus = total(name, profile["resident"])
        transient = profile.get("transient") or []
        trans = [entry(name, s) for s in transient]
        peak_mem = resident_mem + max([t[0] for t in trans], default=0)
        peak_cpus = resident_cpus + max([t[1] for t in trans], default=0.0)
        declared = profile["peak"]
        if peak_mem != declared["memory_mib"] or abs(peak_cpus - float(declared["cpus"])) > 1e-9:
            fail(
                "register: "
                + name
                + " peak "
                + str((declared["memory_mib"], float(declared["cpus"])))
                + " does not match its parts "
                + str((peak_mem, round(peak_cpus, 6)))
            )
        reduced = profile.get("reduced_variant")
        if isinstance(reduced, dict):
            drops = set(reduced.get("drops") or [])
            kept = [s for s in profile["resident"] if s not in drops]
            r_mem, r_cpus = total(name, kept)
            r_peak_mem = r_mem + max([t[0] for t in trans], default=0)
            r_peak_cpus = r_cpus + max([t[1] for t in trans], default=0.0)
            declared_r = reduced["peak"]
            if (
                r_peak_mem != declared_r["memory_mib"]
                or abs(r_peak_cpus - float(declared_r["cpus"])) > 1e-9
            ):
                fail("register: " + name + " reduced peak does not match its parts")


def main() -> int:
    with open(REGISTER, encoding="utf-8") as handle:
        register = yaml.safe_load(handle)
    lock = load_tools_lock()

    files = sorted(glob.glob(os.path.join(COMPOSE_DIR, "*.yml")))
    if not files:
        fail("no compose files under deployment/compose/")

    seen_profiles = set()
    for path in files:
        relative = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        if not isinstance(document, dict) or "services" not in document:
            fail(relative + ": not a compose document")
            continue
        profile = PROFILE_OF_PROJECT.get(document.get("name"))
        if profile is None:
            fail(
                relative
                + ": name "
                + repr(document.get("name"))
                + " does not map to a register profile"
            )
            continue
        seen_profiles.add(profile)
        check_subset(relative, document)
        check_images(relative, document, lock)
        check_limits(relative, profile, document, register)
        check_clickhouse_limits(relative, path, profile, document, register)

    missing = set(register["profiles"]) - seen_profiles
    if missing:
        fail("no compose file declares the profile(s): " + ", ".join(sorted(missing)))

    check_image_runtimes(lock)
    check_service_classification(files, lock)
    check_shared_service_bodies(files)
    check_peaks(register)

    if failures:
        for message in failures:
            print("FAIL " + message, file=sys.stderr)
        print(str(len(failures)) + " compose-subset failure(s)", file=sys.stderr)
        return 1
    print(
        "compose-subset lint: " + str(len(files)) + " compose file(s) checked, all limits resolve, "
        "all peaks recompute, all images pinned"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
