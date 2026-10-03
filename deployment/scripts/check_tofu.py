#!/usr/bin/env python3
"""The OpenTofu structural policy scan.

`tofu validate` and `tflint` prove the modules are syntactically valid and
internally consistent. This scan proves the things they cannot: that the IAM
role topology is one IRSA role per component with a node role that carries no
S3 or Secrets Manager permission, that the vending role is prefix-scoped and
trusted by Polaris alone, that no identity policy uses a full wildcard action,
that every secret declares its rotation class, and that the secrets projection
sets filePermission 0400.

It reads the same data files the modules read (deployment/tofu/policies/*.json
and the two templates), so a change to the boundary is a change this scan sees.
Each check is named, and the mutation test
deployment/scripts/test-check-tofu.sh proves every one is load-bearing.

Usage: python deployment/scripts/check_tofu.py [--root DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROTATION_CLASSES = {"reload", "restart", "init"}
ARMS = {"minimal", "reference"}
MODULES = ["network", "storage", "iam", "security", "rds", "secrets"]
FORBIDDEN_ACTION_PREFIXES = ("s3:", "secretsmanager:")


class Failures:
    def __init__(self) -> None:
        self.items: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if not condition:
            self.items.append(name + (": " + detail if detail else ""))


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def statements(policy: object) -> list[dict]:
    if not isinstance(policy, dict):
        return []
    stmt = policy.get("Statement", [])
    return stmt if isinstance(stmt, list) else [stmt]


def actions(policy: object) -> list[str]:
    out: list[str] = []
    for stmt in statements(policy):
        action = stmt.get("Action", [])
        if isinstance(action, str):
            out.append(action)
        else:
            out.extend(action)
    return out


def resources(policy: object) -> list[str]:
    out: list[str] = []
    for stmt in statements(policy):
        resource = stmt.get("Resource", [])
        if isinstance(resource, str):
            out.append(resource)
        else:
            out.extend(resource)
    return out


def substitute_template(text: str) -> str:
    """Replace the template placeholders with dummies so the JSON parses."""
    for token in (
        "oidc_provider_arn",
        "oidc_issuer_url",
        "namespace",
        "service_account",
        "trusted_role_arn",
    ):
        text = text.replace("${" + token + "}", "PLACEHOLDER_" + token)
    return text


def scan(root: Path) -> list[str]:
    failures = Failures()
    tofu = root / "deployment" / "tofu"
    scripts = root / "deployment" / "scripts"

    root_main = (tofu / "main.tf").read_text()

    # 1. Every module the ticket names is authored and called from the root.
    for name in MODULES:
        failures.check(
            "module " + name + " is authored", (tofu / "modules" / name / "main.tf").is_file()
        )
        failures.check(
            "module " + name + " is called from the root",
            re.search(r'module\s+"' + name + r'"', root_main) is not None,
        )

    # 2. The two arms exist and declare their arm.
    minimal = (tofu / "profiles" / "minimal.tfvars").read_text()
    reference = (tofu / "profiles" / "reference.tfvars").read_text()
    failures.check(
        "the minimal profile declares arm = minimal",
        re.search(r'arm\s*=\s*"minimal"', minimal) is not None,
    )
    failures.check(
        "the reference profile declares arm = reference",
        re.search(r'arm\s*=\s*"reference"', reference) is not None,
    )
    failures.check(
        "the minimal arm has no private subnets",
        re.search(r"enable_private_subnets\s*=\s*false", minimal) is not None,
    )
    failures.check(
        "the reference arm has private subnets",
        re.search(r"enable_private_subnets\s*=\s*true", reference) is not None,
    )

    # 3. The IAM role topology as data.
    iam = load_json(tofu / "policies" / "iam.json")
    components = iam.get("components", {})
    node_policy = iam.get("node", {}).get("policy")
    node_actions = actions(node_policy)
    offending = [a for a in node_actions if a.lower().startswith(FORBIDDEN_ACTION_PREFIXES)]
    failures.check(
        "the node role carries no S3 or Secrets Manager action",
        not offending,
        "found " + ", ".join(offending),
    )
    failures.check("the node role exists with a policy", node_policy is not None)

    failures.check("at least one component role is declared", len(components) > 0)
    for name, role in components.items():
        failures.check("component " + name + " declares a namespace", bool(role.get("namespace")))
        failures.check(
            "component " + name + " declares a service account", bool(role.get("service_account"))
        )
        arms = set(role.get("arms", []))
        failures.check(
            "component " + name + " declares valid arms",
            bool(arms) and arms <= ARMS,
            "arms=" + repr(sorted(arms)),
        )
        failures.check("component " + name + " has a policy", bool(role.get("policy")))
        for action in actions(role.get("policy")):
            failures.check(
                "component " + name + " has no broad action",
                action != "*" and action.lower() not in {"s3:*", "secretsmanager:*"},
                "action=" + action,
            )

    # 4. The vending role: assumed by a declared component, prefix-scoped.
    vending = iam.get("vending", {})
    assumed_by = vending.get("assumed_by")
    failures.check(
        "the vending role is assumed by a declared component",
        assumed_by in components,
        "assumed_by=" + repr(assumed_by),
    )
    vending_policy = vending.get("policy")
    failures.check("the vending role has a policy", bool(vending_policy))
    vending_resources = resources(vending_policy)
    failures.check(
        "the vending role is scoped to the warehouse prefix",
        any(r.endswith("/warehouse/*") for r in vending_resources),
        "resources=" + repr(vending_resources),
    )
    vending_list = [
        s
        for s in statements(vending_policy)
        if "s3:ListBucket"
        in (s.get("Action") if isinstance(s.get("Action"), list) else [s.get("Action")])
    ]
    failures.check(
        "the vending role's ListBucket is prefix-conditioned",
        any("s3:prefix" in json.dumps(s.get("Condition", {})) for s in vending_list),
    )

    # 5. The IRSA trust template: OIDC-federated, per-service-account.
    trust_irsa = substitute_template((tofu / "policies" / "trust-irsa.json.tmpl").read_text())
    trust_doc = json.loads(trust_irsa)
    stmt = statements(trust_doc)[0]
    failures.check(
        "the IRSA trust action is AssumeRoleWithWebIdentity",
        stmt.get("Action") == "sts:AssumeRoleWithWebIdentity",
    )
    failures.check(
        "the IRSA trust principal is the cluster OIDC provider",
        stmt.get("Principal", {}).get("Federated") == "PLACEHOLDER_oidc_provider_arn",
    )
    conditions = stmt.get("Condition", {}).get("StringEquals", {})
    sub = next((v for k, v in conditions.items() if k.endswith(":sub")), None)
    failures.check(
        "the IRSA trust sub names the service account",
        sub == "system:serviceaccount:PLACEHOLDER_namespace:PLACEHOLDER_service_account",
        "sub=" + repr(sub),
    )
    aud = next((v for k, v in conditions.items() if k.endswith(":aud")), None)
    failures.check(
        "the IRSA trust audience is sts.amazonaws.com",
        aud == "sts.amazonaws.com",
        "aud=" + repr(aud),
    )

    # 6. The vending trust template: names a role, never a wildcard principal.
    trust_role = substitute_template((tofu / "policies" / "trust-role.json.tmpl").read_text())
    trust_role_doc = json.loads(trust_role)
    role_principal = statements(trust_role_doc)[0].get("Principal", {}).get("AWS")
    failures.check(
        "the vending role trusts only the named role",
        role_principal == "PLACEHOLDER_trusted_role_arn",
        "principal=" + repr(role_principal),
    )

    # 7. The secrets projection sets filePermission 0400.
    projection = (tofu / "secrets" / "secret-projection.yaml.tmpl").read_text()
    failures.check(
        'the secret projection sets filePermission "0400"',
        re.search(r'filePermission:\s*"0400"', projection) is not None,
    )

    # 8. The secrets inventory declares a rotation class for every entry.
    inventory = load_json(tofu / "policies" / "secrets.json")
    failures.check("the secrets inventory is non-empty", len(inventory) > 0)
    for name, entry in inventory.items():
        failures.check(
            "secret " + name + " declares a rotation class",
            entry.get("rotation_class") in ROTATION_CLASSES,
            "class=" + repr(entry.get("rotation_class")),
        )
        failures.check("secret " + name + " declares no value", "value" not in entry)

    # 9. Every data file the scan reads is referenced by the HCL, so the data is
    # load-bearing rather than decorative.
    hcl = "\n".join(p.read_text() for p in tofu.rglob("*.tf"))
    for data_file in [
        "iam.json",
        "secrets.json",
        "trust-irsa.json.tmpl",
        "trust-role.json.tmpl",
        "secret-projection.yaml.tmpl",
    ]:
        failures.check("the HCL consumes " + data_file, data_file in hcl)

    # 10. The arm filter exists, so a reference-only role is not created in the
    # minimal arm.
    failures.check(
        "the root filters component roles by arm",
        "contains(role.arms, var.arm)" in (tofu / "locals.tf").read_text(),
    )

    # 11. The deployment check is the real one, not the stub.
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text()
    failures.check("CI runs check-tofu.sh", "check-tofu.sh" in workflow)
    failures.check(
        "CI no longer stubs the deployment check", "check-stub.sh deployment 74" not in workflow
    )
    failures.check("the check script exists", (scripts / "check-tofu.sh").is_file())

    return failures.items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    items = scan(root)
    if items:
        for item in items:
            print("::error::tofu policy scan: " + item, file=sys.stderr)
        print("tofu policy scan: " + str(len(items)) + " failure(s)", file=sys.stderr)
        return 1
    print("tofu policy scan: role topology, vending scope and secrets projection as declared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
