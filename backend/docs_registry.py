"""Registry of tool documentation .md files. Add new entries when tools expand."""

from pathlib import Path

# Project root (parent of backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Extensible registry: id, path (relative to project root), title
# Add new entries when tools expand.
DOC_REGISTRY = [
    {"id": "tml_data_loader", "path": "docs/functions/TML_DATA_LOADER.md", "title": "TML Data Loader"},
    {"id": "deactive_cml", "path": "docs/functions/DEACTIVE_CML.md", "title": "De-active CML"},
    {"id": "ili_visual_tool", "path": "docs/functions/ILI_VISUAL_TOOL.md", "title": "ILI Visual Tool"},
    {"id": "metal_loss_assessment", "path": "docs/functions/METAL_LOSS_MASS_ASSESSMENT.md", "title": "Metal Loss Mass Assessment"},
    {"id": "backend_api", "path": "docs/functions/BACKEND_API.md", "title": "Backend API"},
    {"id": "dashboard", "path": "docs/functions/DASHBOARD.md", "title": "Dashboard"},
    {"id": "facility", "path": "docs/functions/FACILITY.md", "title": "Facility"},
    {"id": "frontend_components", "path": "docs/functions/FRONTEND_COMPONENTS.md", "title": "Frontend Components"},
    {"id": "architecture", "path": "docs/ARCHITECTURE.md", "title": "Architecture"},
    {"id": "docs_readme", "path": "docs/README.md", "title": "Documentation Hub"},
]


def get_doc_path(entry: dict) -> Path:
    """Resolve full path for a registry entry."""
    return _PROJECT_ROOT / entry["path"]
