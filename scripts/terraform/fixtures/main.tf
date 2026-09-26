terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "2.5.3"
    }
  }
}

resource "local_file" "fixture" {
  filename        = "${path.module}/fixture.txt"
  content         = "original"
  file_permission = "0600"
}
