"""
Web-based 3D viewer server for PLY point clouds and meshes.

Launch:
    python -m spatial.viewer.server
    python -m spatial.viewer.server --port 8080
"""

import os
import sys
import io
import argparse
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Resolve project paths
_THIS_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _THIS_DIR / "static"
_PROJECT_ROOT = _THIS_DIR.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_PROJECTS_DIR = _DATA_DIR / "projects"

app = FastAPI(
    title="Spatial Awareness Viewer",
    version="0.1.0",
    description="Web-based 3D viewer for PLY point clouds and meshes",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_resolve(base: Path, rel: str) -> Path:
    """Resolve a relative path under base, preventing directory traversal."""
    resolved = (base / rel).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    return resolved


@app.get("/api/projects")
def list_projects():
    """List all project directories under data/projects/."""
    if not _PROJECTS_DIR.is_dir():
        return {"projects": []}

    projects = []
    for entry in sorted(_PROJECTS_DIR.iterdir()):
        if entry.is_dir():
            ply_files = list(entry.rglob("*.ply"))
            glb_files = list(entry.rglob("*.glb")) + list(entry.rglob("*.gltf"))
            projects.append({
                "id": entry.name,
                "path": str(entry),
                "ply_count": len(ply_files),
                "glb_count": len(glb_files),
            })

    return {"projects": projects}


@app.get("/api/projects/{project_id}/files")
def list_project_files(project_id: str):
    """List output files (PLY, GLB, GLTF) for a given project."""
    project_dir = _safe_resolve(_PROJECTS_DIR, project_id)
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    files = []
    for pattern in ("*.ply", "*.glb", "*.gltf", "*.obj"):
        for f in sorted(project_dir.rglob(pattern)):
            rel = f.relative_to(_PROJECTS_DIR)
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(rel).replace("\\", "/"),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "extension": f.suffix.lower(),
                "relative_dir": str(f.parent.relative_to(project_dir)).replace("\\", "/"),
            })

    return {"project_id": project_id, "files": files}


@app.get("/api/files/{path:path}")
def serve_file(path: str):
    """Serve a PLY/GLB/GLTF/OBJ file from the projects directory."""
    file_path = _safe_resolve(_PROJECTS_DIR, path)

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    suffix = file_path.suffix.lower()
    content_types = {
        ".ply": "application/octet-stream",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".obj": "text/plain",
    }
    media_type = content_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.get("/api/convert/{path:path}")
def convert_to_gltf(path: str):
    """Convert a PLY file to GLB (binary glTF) on the fly using trimesh."""
    file_path = _safe_resolve(_PROJECTS_DIR, path)

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    if file_path.suffix.lower() != ".ply":
        raise HTTPException(status_code=400, detail="Only PLY files can be converted")

    try:
        import trimesh
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="trimesh not installed. Run: pip install trimesh",
        )

    try:
        scene_or_mesh = trimesh.load(str(file_path))

        if isinstance(scene_or_mesh, trimesh.Scene):
            scene = scene_or_mesh
        elif isinstance(scene_or_mesh, trimesh.PointCloud):
            scene = trimesh.Scene(geometry=scene_or_mesh)
        elif isinstance(scene_or_mesh, trimesh.Trimesh):
            scene = trimesh.Scene(geometry=scene_or_mesh)
        else:
            scene = trimesh.Scene(geometry=scene_or_mesh)

        glb_data = scene.export(file_type="glb")

        return Response(
            content=glb_data,
            media_type="model/gltf-binary",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Content-Disposition": f'inline; filename="{file_path.stem}.glb"',
                "Cache-Control": "public, max-age=3600",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@app.get("/api/file-info/{path:path}")
def file_info(path: str):
    """Return metadata about a PLY file without sending the full content."""
    file_path = _safe_resolve(_PROJECTS_DIR, path)

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    stat = file_path.stat()
    info = {
        "name": file_path.name,
        "path": path,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "extension": file_path.suffix.lower(),
    }

    if file_path.suffix.lower() == ".ply":
        try:
            header_info = _parse_ply_header(file_path)
            info.update(header_info)
        except Exception:
            pass

    return info


def _parse_ply_header(file_path: Path) -> dict:
    """Parse the PLY header for vertex/face counts and format info."""
    result = {
        "format": "unknown",
        "vertex_count": 0,
        "face_count": 0,
        "has_colors": False,
        "has_normals": False,
    }

    try:
        with open(file_path, "rb") as f:
            header_bytes = b""
            while True:
                line = f.readline()
                header_bytes += line
                if line.strip() == b"end_header":
                    break
                if len(header_bytes) > 4096:
                    break

        header = header_bytes.decode("ascii", errors="replace")
        in_vertex_element = False

        for line in header.split("\n"):
            line = line.strip()
            if line.startswith("format "):
                result["format"] = line.split(" ", 1)[1]
            elif line.startswith("element vertex "):
                result["vertex_count"] = int(line.split()[-1])
                in_vertex_element = True
            elif line.startswith("element face "):
                result["face_count"] = int(line.split()[-1])
                in_vertex_element = False
            elif line.startswith("element "):
                in_vertex_element = False
            elif in_vertex_element and line.startswith("property "):
                parts = line.split()
                if len(parts) >= 3:
                    prop_name = parts[-1]
                    if prop_name in ("red", "green", "blue", "r", "g", "b"):
                        result["has_colors"] = True
                    if prop_name in ("nx", "ny", "nz"):
                        result["has_normals"] = True

    except Exception:
        pass

    return result


# Mount static files last so API routes take priority
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the viewer server."""
    print(f"\n  Spatial Awareness - 3D Viewer")
    print(f"  ==============================")
    print(f"  Server:   http://localhost:{port}")
    print(f"  Projects: {_PROJECTS_DIR}")
    print(f"  Static:   {_STATIC_DIR}")
    print()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spatial Awareness 3D Viewer Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
