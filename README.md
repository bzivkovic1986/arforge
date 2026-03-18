# ARForge

ARForge is a lightweight, YAML-first AUTOSAR Classic modeling tool. It lets you describe a project in YAML, validate it deterministically, and export ARXML from the validated internal model.

## Why ARForge Exists

ARForge is designed for teams that want AUTOSAR modeling to work well in normal software engineering workflows: readable text files, stable diffs, automated validation, and CI-friendly export.

## Current Scope

The current implementation targets a practical AUTOSAR Classic 4.2 subset centered on:

- project manifests and scaffold generation
- base, implementation, and application data types
- units and compu methods
- sender-receiver and client-server interfaces
- SWC types with ports, runnables, events, and ComSpec
- system composition instances and port-level connectors
- semantic validation with stable finding codes
- monolithic or split ARXML export

## Quickstart

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Example workflow:

```bash
python -m arforge.cli init demo-system
python -m arforge.cli validate examples/autosar.project.yaml
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc
```

Run tests with:

```bash
pytest -q
```

## Documentation

Start with [docs/index.md](docs/index.md).

- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Modeling Concepts](docs/modeling-concepts.md)
- [Project Structure](docs/project-structure.md)
- [Validation](docs/validation.md)
- [CLI](docs/cli.md)
- [Roadmap](docs/roadmap.md)

## Contributing

Issues and pull requests are welcome. For contribution expectations and the maintainer-led project model, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Licensed under [Apache-2.0](LICENSE).

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md) for project independence and affiliation notes.

## Contact

For questions, feedback, collaboration, or support, contact:

Bojan Zivkovic  
Email: [bojan.zivkovic.ns@gmail.com](mailto:bojan.zivkovic.ns@gmail.com)  
LinkedIn: [www.linkedin.com/in/bojanzivkovic86](https://www.linkedin.com/in/bojanzivkovic86)
