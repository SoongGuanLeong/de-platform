variable "name_prefix" {
  description = "Prefix for every role name."
  type        = string
}

variable "oidc_provider_arn" {
  description = "The EKS cluster's IAM OIDC provider ARN."
  type        = string
}

variable "oidc_issuer_url" {
  description = "The EKS cluster's OIDC issuer URL."
  type        = string
}

variable "iam" {
  description = "The role topology as data: the node role, the vending role and the component policies."
  type        = any
}

variable "roles" {
  description = "The component roles this arm creates, already filtered by arm."
  type        = any
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
}
