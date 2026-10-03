variable "name_prefix" {
  description = "Prefix for every security group."
  type        = string
}

variable "vpc_id" {
  description = "The VPC the security groups belong to."
  type        = string
}

variable "enable_alb" {
  description = "Whether the ALB security group exists (reference arm only)."
  type        = bool
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
}
