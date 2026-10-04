variable "name_prefix" {
  description = "Prefix for every secret name."
  type        = string
}

variable "inventory" {
  description = "The secret inventory: name to its component and rotation class."
  type = map(object({
    component      = string
    rotation_class = string
  }))
}

variable "enabled" {
  description = "The secrets this arm creates."
  type        = list(string)
}

variable "projection_component" {
  description = "The component the example CSI projection is rendered for: only its secrets are projected."
  type        = string
}

variable "kms_key_arn" {
  description = "The CMK encrypting the secrets."
  type        = string
}

variable "region" {
  description = "The region the CSI provider reads from."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
}
