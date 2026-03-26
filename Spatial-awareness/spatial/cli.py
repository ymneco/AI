"""CLI commands for Spatial Awareness."""

import os
import sys

import typer
from rich.console import Console
from rich.table import Table

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = typer.Typer(
    name="spatial",
    help="3D reconstruction from smartphone video/images",
    no_args_is_help=True,
)
console = Console()


@app.command()
def reconstruct(
    input_path: str = typer.Argument(
        ..., help="Path to video file or image directory",
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Output directory (default: data/projects/<id>)",
    ),
    fps: float = typer.Option(
        2.0, "--fps", "-f",
        help="Frames per second to extract from video",
    ),
    strategy: str = typer.Option(
        "uniform", "--strategy", "-s",
        help="Frame extraction strategy: uniform, keyframe, adaptive",
    ),
    matcher: str = typer.Option(
        "exhaustive", "--matcher", "-m",
        help="Feature matching: exhaustive (thorough) or sequential (fast for video)",
    ),
    max_frames: int = typer.Option(
        None, "--max-frames",
        help="Maximum number of frames to extract",
    ),
    max_image_size: int = typer.Option(
        3200, "--max-size",
        help="Maximum image dimension (longest edge, px)",
    ),
    no_gpu: bool = typer.Option(
        False, "--no-gpu",
        help="Disable GPU acceleration",
    ),
    no_dense: bool = typer.Option(
        False, "--no-dense",
        help="Skip dense reconstruction (sparse only)",
    ),
    no_mesh: bool = typer.Option(
        False, "--no-mesh",
        help="Skip mesh generation",
    ),
    dense_max_size: int = typer.Option(
        2000, "--dense-max-size",
        help="Max image size for dense reconstruction",
    ),
    mesh_method: str = typer.Option(
        "poisson", "--mesh-method",
        help="Mesh method: poisson or delaunay",
    ),
    project_id: str = typer.Option(
        None, "--project-id",
        help="Custom project ID (auto-generated if not set)",
    ),
):
    """
    Reconstruct 3D model from video or images.

    Examples:
        python main.py reconstruct factory_video.mp4
        python main.py reconstruct ./photos/ --matcher sequential
        python main.py reconstruct video.mp4 --fps 1 --strategy keyframe
        python main.py reconstruct video.mp4 --no-dense  (sparse only, fast)
    """
    from spatial.utils.logging_config import setup_logging
    setup_logging("INFO")

    from spatial.pipeline.runner import PipelineRunner, PipelineConfig

    console.print(f"\n[bold]Spatial Awareness[/bold] - 3D Reconstruction\n")

    # Validate input
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        console.print(f"[red]Error:[/red] Input not found: {input_path}")
        raise typer.Exit(1)

    if os.path.isfile(input_path):
        size_mb = os.path.getsize(input_path) / (1024 * 1024)
        console.print(f"  Input: [cyan]{os.path.basename(input_path)}[/cyan] (video, {size_mb:.0f} MB)")
    else:
        n_images = len([
            f for f in os.listdir(input_path)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff"))
        ])
        console.print(f"  Input: [cyan]{input_path}[/cyan] ({n_images} images)")

    console.print(f"  Strategy: {strategy} | FPS: {fps} | Matcher: {matcher}")
    console.print(f"  GPU: {'[green]enabled[/green]' if not no_gpu else '[yellow]disabled[/yellow]'}")
    console.print(f"  Dense: {'[green]enabled[/green]' if not no_dense else '[yellow]disabled[/yellow]'}")
    console.print(f"  Mesh: {'[green]enabled[/green]' if not no_mesh else '[yellow]disabled[/yellow]'}")
    console.print()

    config = PipelineConfig(
        input_path=input_path,
        fps=fps,
        strategy=strategy,
        max_frames=max_frames,
        max_image_size=max_image_size,
        use_gpu=not no_gpu,
        matcher=matcher,
        enable_dense=not no_dense,
        dense_max_image_size=dense_max_size,
        enable_mesh=not no_mesh,
        mesh_method=mesh_method,
    )

    runner = PipelineRunner(
        projects_dir=output if output else None,
    )

    result = runner.run(config, project_id=project_id)

    # Display results
    console.print()
    if result.success:
        table = Table(title="Reconstruction Complete")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Project ID", result.project_id)
        table.add_row("Images registered", str(result.num_images))
        table.add_row("Sparse points", f"{result.num_sparse_points:,}")
        if result.num_dense_points:
            table.add_row("Dense points", f"{result.num_dense_points:,}")
        table.add_row("Time", f"{result.total_elapsed_sec:.1f} sec")
        if result.sparse_ply:
            table.add_row("Sparse PLY", result.sparse_ply)
        if result.dense_ply:
            table.add_row("Dense PLY", result.dense_ply)
        if result.mesh_ply:
            table.add_row("Mesh PLY", result.mesh_ply)
        table.add_row("Output dir", result.output_dir)
        console.print(table)

        # Stage summary
        console.print()
        for s in result.stages:
            icon = {"completed": "[green]OK[/green]", "failed": "[red]FAIL[/red]",
                    "skipped": "[dim]SKIP[/dim]"}.get(s.status, "[yellow]?[/yellow]")
            console.print(f"  {icon} {s.stage.value}: {s.message}")

        console.print(
            "\n[dim]View point cloud: python main.py view <path-to-ply>[/dim]\n"
        )
    else:
        console.print(f"[red]Reconstruction failed:[/red] {result.error}")
        for s in result.stages:
            if s.status == "failed":
                console.print(f"  [red]Failed at: {s.stage.value}[/red] — {s.message}")
        console.print("\n[dim]Troubleshooting tips:[/dim]")
        console.print("  - Ensure the video has enough visual overlap between frames")
        console.print("  - Try different fps (--fps 1) or strategy (--strategy keyframe)")
        console.print("  - Try --no-dense for sparse-only reconstruction")
        raise typer.Exit(1)


@app.command()
def info():
    """Show system information and tool availability."""
    from spatial.utils.logging_config import setup_logging
    setup_logging("WARNING")

    console.print("\n[bold]Spatial Awareness[/bold] - System Info\n")

    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")

    # Python
    table.add_row("Python", f"[green]{sys.version.split()[0]}[/green]", sys.executable)

    # FFmpeg
    from spatial.utils.platform_compat import find_binary
    ffmpeg = find_binary("ffmpeg", "FFMPEG_PATH")
    if ffmpeg:
        table.add_row("FFmpeg", "[green]found[/green]", ffmpeg)
    else:
        table.add_row("FFmpeg", "[red]not found[/red]", "Install FFmpeg")

    # COLMAP
    colmap = find_binary("colmap", "COLMAP_PATH")
    if colmap:
        table.add_row("COLMAP", "[green]found[/green]", colmap)
    else:
        table.add_row(
            "COLMAP", "[red]not found[/red]",
            "Run: python scripts/install_colmap.py",
        )

    # CUDA
    from spatial.utils.gpu import check_nvidia_smi
    gpu_info = check_nvidia_smi()
    if gpu_info:
        table.add_row(
            "GPU",
            "[green]available[/green]",
            f"{gpu_info['name']} ({gpu_info['memory_mb']} MB)",
        )
    else:
        table.add_row("GPU", "[yellow]not detected[/yellow]", "CPU mode will be used")

    # PyTorch
    try:
        import torch
        cuda_str = f"CUDA {torch.version.cuda}" if torch.cuda.is_available() else "CPU only"
        table.add_row("PyTorch", f"[green]{torch.__version__}[/green]", cuda_str)
    except ImportError:
        table.add_row("PyTorch", "[yellow]not installed[/yellow]", "Optional (for future features)")

    # Open3D
    try:
        import open3d
        table.add_row("Open3D", f"[green]{open3d.__version__}[/green]", "")
    except ImportError:
        table.add_row("Open3D", "[yellow]not installed[/yellow]", "pip install open3d")

    console.print(table)
    console.print()


@app.command()
def view(
    ply_path: str = typer.Argument(..., help="Path to PLY file to view"),
):
    """View a PLY point cloud or mesh in Open3D viewer."""
    if not os.path.isfile(ply_path):
        console.print(f"[red]Error:[/red] File not found: {ply_path}")
        raise typer.Exit(1)

    try:
        import open3d as o3d
    except ImportError:
        console.print("[red]Error:[/red] Open3D not installed. Run: pip install open3d")
        raise typer.Exit(1)

    console.print(f"Loading {ply_path}...")

    # Try as point cloud first, then as mesh
    pcd = o3d.io.read_point_cloud(ply_path)
    if len(pcd.points) > 0:
        console.print(f"  Type: Point Cloud")
        console.print(f"  Points: {len(pcd.points):,}")
        console.print(f"  Has colors: {pcd.has_colors()}")
        console.print("Opening viewer...")
        o3d.visualization.draw_geometries(
            [pcd], window_name="Spatial Awareness - Point Cloud",
        )
    else:
        mesh = o3d.io.read_triangle_mesh(ply_path)
        if len(mesh.vertices) > 0:
            console.print(f"  Type: Triangle Mesh")
            console.print(f"  Vertices: {len(mesh.vertices):,}")
            console.print(f"  Triangles: {len(mesh.triangles):,}")
            console.print(f"  Has colors: {mesh.has_vertex_colors()}")
            console.print("Opening viewer...")
            mesh.compute_vertex_normals()
            o3d.visualization.draw_geometries(
                [mesh], window_name="Spatial Awareness - Mesh",
            )
        else:
            console.print("[red]Error:[/red] No geometry found in file")
            raise typer.Exit(1)


@app.command()
def serve(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
):
    """Start the web viewer server."""
    try:
        from spatial.viewer.server import run_server
    except ImportError as e:
        console.print(f"[red]Error:[/red] Missing dependency: {e}")
        console.print("[dim]Install with: pip install 'spatial-awareness[api]'[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Spatial Awareness[/bold] - Web 3D Viewer\n")
    console.print(f"  Open: [cyan]http://localhost:{port}[/cyan]")
    console.print(f"  Press Ctrl+C to stop.\n")
    run_server(host=host, port=port)
