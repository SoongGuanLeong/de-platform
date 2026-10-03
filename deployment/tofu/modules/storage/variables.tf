variable "name_prefix" {
  description = "Prefix for every bucket and key."
  type        = string
}

variable "buckets" {
  description = "The bucket per concern: a map of concern name to its suffix, versioning and lifecycle."
  type = map(object({
    suffix          = string
    versioned       = bool
    expiration_days = number
  }))
}

variable "capacity_gb" {
  description = "The arm's declared S3 budget in GB."
  type        = number
}

variable "enable_ecr" {
  description = "Whether the authored-but-unused ECR repository exists (reference arm only, ADR-0034)."
  type        = bool
}

variable "ecr_repo_name" {
  description = "The ECR repository name."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
}
