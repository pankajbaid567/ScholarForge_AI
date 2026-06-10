terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "scholarforge-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------
# VPC Network Infrastructure
# ---------------------------------------------------------
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "scholarforge-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

# ---------------------------------------------------------
# EKS Cluster (Kubernetes)
# ---------------------------------------------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "scholarforge-cluster"
  cluster_version = "1.29"

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    general = {
      desired_size = 2
      min_size     = 1
      max_size     = 5

      instance_types = ["t3.xlarge"] # Required for high memory ChromaDB and Worker nodes
    }
  }
}

# ---------------------------------------------------------
# Managed Redis (ElastiCache)
# ---------------------------------------------------------
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "scholarforge-redis"
  engine               = "redis"
  node_type            = "cache.m5.large" # Needs memory for RedisVL Semantic Cache
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis_subnet.name
}

resource "aws_elasticache_subnet_group" "redis_subnet" {
  name       = "scholarforge-redis-subnet"
  subnet_ids = module.vpc.private_subnets
}

# ---------------------------------------------------------
# Managed PostgreSQL (RDS)
# ---------------------------------------------------------
resource "aws_db_instance" "postgres" {
  identifier           = "scholarforge-db"
  allocated_storage    = 20
  engine               = "postgres"
  engine_version       = "15.3"
  instance_class       = "db.t3.medium"
  db_name              = "scholarforge"
  username             = var.db_username
  password             = var.db_password
  skip_final_snapshot  = true
  db_subnet_group_name = aws_db_subnet_group.postgres_subnet.name
}

resource "aws_db_subnet_group" "postgres_subnet" {
  name       = "scholarforge-postgres-subnet"
  subnet_ids = module.vpc.private_subnets
}
