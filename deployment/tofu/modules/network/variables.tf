variable "name_prefix" {
  description = "Prefix for every named resource."
  type        = string
}

variable "region" {
  description = "The AWS region, for the S3 gateway endpoint's service name."
  type        = string
}

variable "vpc_cidr" {
  description = "The arm's VPC CIDR."
  type        = string
}

variable "azs" {
  description = "The Availability Zones the arm spans."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "One public subnet CIDR per Availability Zone."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "One private subnet CIDR per Availability Zone; used only when enable_private is true."
  type        = list(string)
}

variable "enable_private" {
  description = "Whether private subnets and one NAT gateway per AZ are created."
  type        = bool
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
}
