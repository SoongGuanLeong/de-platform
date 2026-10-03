# One provider, one region. The region is a variable because both arms are
# modelled in ap-southeast-5 and the document carries us-east-1 only as a cost
# comparison, not as an authored arm.
provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}
