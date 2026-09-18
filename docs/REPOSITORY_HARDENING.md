# Repository hardening checklist

The source tree already contains CodeQL, Dependabot, CODEOWNERS, least-
privilege build/release jobs and a security policy.

The following controls live in GitHub repository settings and should also be
enabled by an administrator.

## Main branch

Create a branch protection rule or repository ruleset for `main`:

- require a pull request before merging for normal collaborative development;
- require status checks to pass;
- include the Windows build/smoke test and CodeQL checks;
- require branches to be up to date before merge;
- block force pushes;
- block branch deletion;
- require conversation resolution;
- apply the rule to administrators if the repository becomes collaborative.

For a single-owner rapid-development workflow, direct pushes may remain
enabled temporarily, but force-push and deletion protection are still useful.

## Security settings

Enable where available:

- Dependency graph;
- Dependabot alerts;
- Dependabot security updates;
- Code scanning;
- Secret scanning;
- Push protection for secrets;
- Private vulnerability reporting.

## Account security

The repository is only as secure as the maintainer account:

- enable strong 2FA or passkeys;
- keep recovery codes offline;
- review active GitHub Apps and OAuth grants;
- remove unused deploy keys and personal access tokens;
- never commit Authenticode/private signing keys.

## Release signing

For stronger Windows trust, obtain an Authenticode code-signing certificate.

The private signing key must be stored outside the repository, ideally in a
hardware-backed or managed signing service. The release workflow can then sign
`Pantallas.exe` and `PantallasSetup.exe` before publishing them.

## Source confidentiality

A public repository cannot technically prevent source download. If protecting
implementation details becomes more important than public development,
separate the project into:

1. a private source repository; and
2. a public distribution repository containing signed releases, checksums,
   documentation and update metadata only.
