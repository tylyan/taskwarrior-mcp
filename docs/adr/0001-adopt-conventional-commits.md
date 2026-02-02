# ADR-0001: Adopt Conventional Commits

## Status

Accepted

## Context

The taskwarrior-mcp project has grown to include 21 tools across core task management and agent intelligence categories. As development continues (often with AI assistance), tracking what changed and why becomes increasingly important.

Current state:
- Commits use imperative style ("Add X", "Refactor Y") without structure
- No CHANGELOG.md exists
- No documentation of architectural decisions

Problems this creates:
- Difficult to generate meaningful changelogs automatically
- No semantic understanding of change impact (breaking vs feature vs fix)
- AI assistants cannot determine appropriate commit types
- Manual changelog maintenance is error-prone and often forgotten
- Context about "why" decisions were made gets lost over time

## Decision

Adopt the [Conventional Commits](https://www.conventionalcommits.org/) specification v1.0.0 for all commits.

Implementation:
1. **gitlint** for validation (Python-native, integrates with pre-commit)
2. **git-cliff** for automated changelog generation
3. **CONTRIBUTING.md** documenting the process
4. **ADRs** for capturing significant design decisions

We chose gitlint over commitlint (Node.js) because:
- Python-native, fits the project ecosystem
- Integrates with existing pre-commit configuration
- No npm/node_modules required
- Sufficient feature set for our needs

We chose git-cliff over release-please/semantic-release because:
- Does not couple changelog to automated releases
- Highly configurable output format
- Handles legacy non-conventional commits via regex mapping
- Maintains manual control over release timing

## Consequences

### Positive

- Automated, consistent changelog generation
- Clear communication of change impact (feat vs fix vs chore)
- AI assistants can follow documented conventions
- Breaking changes are explicitly marked with `!` suffix
- Historical context preserved in ADRs

### Negative

- Slight learning curve for new contributors
- Existing commits don't follow the format (mitigated by git-cliff mapping)
- Additional pre-commit hook increases commit validation time slightly

### Neutral

- CI pipeline adds commit message validation step for PRs
- Legacy commits still generate changelog entries via regex patterns

## References

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [gitlint](https://jorisroovers.com/gitlint/)
- [git-cliff](https://git-cliff.org/)
- [Keep a Changelog](https://keepachangelog.com/)
