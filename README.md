# ARForge

ARForge is an AUTOSAR Classic 4.2 YAML-to-ARXML tool.

Pipeline:

`YAML -> JSON Schema validation -> semantic validation -> internal model -> Jinja2 -> ARXML`

## Quickstart

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

Validate:

```bash
python -m arforge.cli validate examples/autosar.project.yaml
```

Export (split):

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc
```

Run tests:

```bash
pytest -q
```

## Documentation

This README is intentionally concise.  
Detailed documentation is in [`docs/index.md`](docs/index.md):

- overview
- architecture
- YAML model
- types
- validation
- export
- roadmap

## VS Code

Recommended extensions:

- Python (Microsoft)
- YAML (Red Hat)

Workspace settings/tasks/launch configs are in `.vscode/`.

## Contact

For questions, ideas or commerical usage of this project, feel free to reach out:
- Email: bojan.zivkovic.ns@gmail.com
- Linkedin: [Bojan Zivkovic](https://www.linkedin.com/in/bojanzivkovic86)
