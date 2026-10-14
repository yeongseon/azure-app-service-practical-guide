# Artifact Redaction Note

The retained artifact structure and capture dates are preserved. Deployment-specific app names in resource paths are replaced with `<app-name>`, 64-character container instance identifiers with the canonical 64-character lowercase `a` placeholder, and internal registry addresses with `10.0.0.0`. These redactions remove deployment and fleet identifiers without changing the recorded experiment outcomes.
