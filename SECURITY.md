# Security Policy

## Supported version

Security fixes are applied to the latest published build of Pantallas.

## Reporting a vulnerability

Please **do not publish exploit details, credentials, tokens, or proof-of-
concept payloads in a public issue**.

Prefer GitHub's **Security → Report a vulnerability** flow when it is available
for this repository. If private vulnerability reporting is not available,
contact the repository owner privately through GitHub before public disclosure.

Include:

- affected Pantallas build;
- Windows version;
- clear reproduction steps;
- expected and observed behavior;
- impact;
- logs or screenshots with secrets and personal data removed.

## Security principles

Pantallas is designed around these rules:

- no credentials or account tokens are stored in the repository;
- releases are built by GitHub Actions rather than on a developer workstation;
- release installers are accompanied by SHA-256 checksums;
- GitHub Actions jobs use least-privilege permissions;
- dependencies are monitored by Dependabot;
- CodeQL scans source changes;
- the updater only accepts the expected installer asset and validates its
  published checksum before launching it;
- application preferences are stored per-user and do not require elevation.

## Limits

A SHA-256 file hosted in the same compromised repository is not a substitute
for cryptographic code signing. A future production-hardening step is to sign
Windows binaries with an Authenticode certificate and verify a release
signature rooted in a key that is not stored in the source repository.
