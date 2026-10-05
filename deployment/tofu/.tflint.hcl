# The tflint configuration (docs/cloud-architecture.md section 7,
# docs/ci-cd-strategy.md section 10). call_module_type = "local" makes one
# invocation lint the root and the modules it calls, so a rule that only fails
# inside a module still fails the check.
config {
  format           = "compact"
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.49.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
