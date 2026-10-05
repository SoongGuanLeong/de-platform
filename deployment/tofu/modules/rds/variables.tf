variable "name_prefix" {
  description = "Prefix for the instance, subnet group and parameter group."
  type        = string
}

variable "subnet_ids" {
  description = "The subnets the DB subnet group spans."
  type        = list(string)
}

variable "security_group_ids" {
  description = "The security groups attached to the instance."
  type        = list(string)
}

variable "instance_class" {
  description = "The RDS instance class."
  type        = string
}

variable "multi_az" {
  description = "Whether the instance is Multi-AZ."
  type        = bool
}

variable "allocated_storage_gb" {
  description = "The gp3 storage in GB."
  type        = number
}

variable "engine_version" {
  description = "The PostgreSQL engine version line."
  type        = string
}

variable "kms_key_arn" {
  description = "The CMK for storage encryption and the managed master secret."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
}
