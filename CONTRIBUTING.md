# Contributing to ARForge

Thanks for your interest in improving ARForge. Contributions are welcome in the form of issues, bug reports, feature requests, pull requests, tests, and documentation updates.

## Contribution Model

ARForge is a maintainer-led project. Community input is appreciated, but the repository maintainer retains final decision authority for roadmap priorities, architecture direction, and merge decisions.

That keeps the project coherent while still making room for useful external contributions.

## Good Ways to Contribute

- Open an issue for bugs, unclear behavior, validation gaps, or documentation problems.
- Open a feature request for new modeling capabilities or CLI improvements.
- Submit focused pull requests for bug fixes, docs updates, tests, or incremental features.
- Improve examples and invalid fixtures when validation behavior changes.

When working with invalid validation fixtures, follow the guidance in [`examples/invalid/README.md`](/d:/VMs/git/arforge/examples/invalid/README.md).

## Before Starting Larger Changes

Please start with an issue or discussion before implementing larger changes, including:

- new YAML formats
- schema redesigns
- major validation refactors
- exporter structure changes
- CLI behavior changes

Early alignment helps avoid wasted work and keeps the project direction consistent.

## Pull Request Expectations

- Keep PRs focused and reasonably small.
- Follow the existing repository structure and coding style.
- Include tests when behavior changes or new validation rules are added.
- Update relevant docs and examples when user-facing behavior changes.
- Preserve deterministic behavior and stable outputs where applicable.

For new features, the usual implementation order is:

1. update schema
2. extend model
3. implement semantic validation
4. update export logic
5. update examples
6. add or update pytest coverage

## Development Notes

- Python 3.11+
- Run tests with `pytest -q`
- Prefer incremental changes over broad refactors
- Keep validation rules isolated and readable instead of building monolithic checks

## Pull Request Review

Submitting a pull request does not guarantee that it will be merged. Reviews consider project scope, design fit, maintainability, test coverage, and long-term ownership cost.

Even when a PR is not merged as proposed, related ideas or smaller follow-up changes may still be welcome.

## Licensing

By submitting a contribution, you agree that your contribution may be distributed under the repository license, Apache-2.0.
