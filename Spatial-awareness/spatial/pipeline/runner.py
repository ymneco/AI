"""End-to-end reconstruction pipeline orchestrator."""

import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from spatial.utils.logging_config import get_logger

log = get_logger("pipeline")


class PipelineStage(str, Enum):
    FRAME_EXTRACTION = "frame_extraction"
    SPARSE_RECONSTRUCTION = "sparse_reconstruction"
    MODEL_MERGE = "model_merge"
    DENSE_RECONSTRUCTION = "dense_reconstruction"
    MESH_GENERATION = "mesh_generation"
    EXPORT = "export"


@dataclass
class StageStatus:
    stage: PipelineStage
    status: str = "pending"  # pending, running, completed, failed, skipped
    progress: float = 0.0
    message: str = ""
    elapsed_sec: float = 0.0


@dataclass
class PipelineResult:
    project_id: str
    success: bool
    output_dir: str
    stages: list[StageStatus] = field(default_factory=list)
    sparse_ply: str | None = None
    dense_ply: str | None = None
    mesh_ply: str | None = None
    num_images: int = 0
    num_sparse_points: int = 0
    num_dense_points: int = 0
    error: str | None = None
    total_elapsed_sec: float = 0.0


@dataclass
class PipelineConfig:
    """Configuration for reconstruction pipeline."""
    # Frame extraction
    input_path: str = ""  # video or image directory
    fps: float = 2.0
    strategy: str = "uniform"  # uniform, keyframe, adaptive
    max_frames: int | None = None
    max_image_size: int = 3200

    # COLMAP
    use_gpu: bool = True
    sift_max_features: int = 8192
    matcher: str = "exhaustive"

    # Dense reconstruction
    enable_dense: bool = True
    dense_max_image_size: int = 2000

    # Mesh
    enable_mesh: bool = True
    mesh_method: str = "poisson"  # "poisson" or "delaunay"

    # Output
    export_ply: bool = True


ProgressCallback = Callable[[PipelineStage, float, str], None]


class PipelineRunner:
    """Orchestrate the full reconstruction pipeline."""

    def __init__(self, projects_dir: str | None = None):
        from config import PROJECTS_DIR
        self.projects_dir = projects_dir or PROJECTS_DIR

    def run(
        self,
        config: PipelineConfig,
        project_id: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> PipelineResult:
        """
        Run the reconstruction pipeline.

        Args:
            config: Pipeline configuration.
            project_id: Unique project ID (auto-generated if None).
            on_progress: Callback for progress updates.

        Returns:
            PipelineResult with output paths and statistics.
        """
        project_id = project_id or uuid.uuid4().hex[:12]
        project_dir = os.path.join(self.projects_dir, project_id)
        os.makedirs(project_dir, exist_ok=True)

        frames_dir = os.path.join(project_dir, "frames")
        colmap_workspace = os.path.join(project_dir, "colmap")
        output_dir = os.path.join(project_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        stages: list[StageStatus] = []
        start_time = time.time()

        def _notify(stage: PipelineStage, progress: float, message: str):
            if on_progress:
                on_progress(stage, progress, message)
            log.info("[%s] %.0f%% - %s", stage.value, progress * 100, message)

        def _elapsed():
            return time.time() - start_time

        try:
            from spatial.sfm.colmap_runner import ColmapRunner, ColmapConfig

            # === Stage 1: Frame Extraction ===
            stage_status = StageStatus(stage=PipelineStage.FRAME_EXTRACTION, status="running")
            stages.append(stage_status)
            _notify(PipelineStage.FRAME_EXTRACTION, 0.0, "Starting frame extraction...")

            frame_paths = self._extract_frames(config, frames_dir)

            if len(frame_paths) < 3:
                raise ValueError(
                    f"Only {len(frame_paths)} frames extracted. "
                    "Need at least 3 for reconstruction."
                )

            stage_status.status = "completed"
            stage_status.progress = 1.0
            stage_status.message = f"Extracted {len(frame_paths)} frames"
            stage_status.elapsed_sec = _elapsed()
            _notify(PipelineStage.FRAME_EXTRACTION, 1.0, stage_status.message)

            # === Stage 2: Sparse Reconstruction ===
            sfm_stage = StageStatus(stage=PipelineStage.SPARSE_RECONSTRUCTION, status="running")
            stages.append(sfm_stage)
            _notify(PipelineStage.SPARSE_RECONSTRUCTION, 0.0, "Starting sparse reconstruction...")

            colmap_config = ColmapConfig(
                use_gpu=config.use_gpu,
                sift_max_features=config.sift_max_features,
                matcher=config.matcher,
                max_image_size=config.max_image_size,
            )
            colmap = ColmapRunner(config=colmap_config)
            sparse_result = colmap.reconstruct_sparse(
                image_dir=frames_dir,
                workspace=colmap_workspace,
            )

            if not sparse_result.success:
                raise RuntimeError(f"Sparse reconstruction failed: {sparse_result.error}")

            sfm_stage.status = "completed"
            sfm_stage.progress = 1.0
            sfm_stage.message = (
                f"{sparse_result.num_images} images, "
                f"{sparse_result.num_points} points, "
                f"{sparse_result.num_models} model(s)"
            )
            sfm_stage.elapsed_sec = _elapsed() - stage_status.elapsed_sec
            _notify(PipelineStage.SPARSE_RECONSTRUCTION, 1.0, sfm_stage.message)

            # The sparse_dir to use for dense reconstruction
            active_sparse_dir = sparse_result.sparse_dir

            # === Stage 3: Model Merge (if multiple models) ===
            if sparse_result.num_models > 1:
                merge_stage = StageStatus(stage=PipelineStage.MODEL_MERGE, status="running")
                stages.append(merge_stage)
                _notify(PipelineStage.MODEL_MERGE, 0.0, "Attempting model merge...")

                sparse_parent = os.path.dirname(sparse_result.sparse_dir)
                merged = colmap.merge_models(sparse_parent)
                if merged:
                    merged_images, merged_points = colmap._count_model(merged)
                    # Only use merged model if it's better than best single
                    if merged_images > sparse_result.num_images:
                        active_sparse_dir = merged
                        merge_stage.message = (
                            f"Merged: {merged_images} images, {merged_points} points "
                            f"(was {sparse_result.num_images}/{sparse_result.num_points})"
                        )
                        merge_stage.status = "completed"
                        log.info("Using merged model (%d > %d images)", merged_images, sparse_result.num_images)
                    else:
                        merge_stage.message = (
                            f"Merged model worse ({merged_images} imgs) "
                            f"than best single ({sparse_result.num_images} imgs), keeping best"
                        )
                        merge_stage.status = "skipped"
                        log.info("Merged model worse, keeping best single model")
                else:
                    merge_stage.message = "Merge not possible, using best single model"
                    merge_stage.status = "skipped"
                merge_stage.progress = 1.0
                _notify(PipelineStage.MODEL_MERGE, 1.0, merge_stage.message)
            else:
                merge_stage = StageStatus(
                    stage=PipelineStage.MODEL_MERGE, status="skipped",
                    progress=1.0, message="Single model, no merge needed",
                )
                stages.append(merge_stage)

            # === Stage 4: Export sparse PLY ===
            sparse_ply = os.path.join(output_dir, "sparse.ply")
            colmap.export_ply(active_sparse_dir, sparse_ply)

            # === Stage 5: Dense Reconstruction (multi-model) ===
            dense_ply = None
            num_dense_points = 0
            best_dense_dir = None  # for mesh generation
            if config.enable_dense:
                dense_stage = StageStatus(stage=PipelineStage.DENSE_RECONSTRUCTION, status="running")
                stages.append(dense_stage)

                # Collect all qualifying sub-models (5+ images)
                sparse_parent = os.path.dirname(sparse_result.sparse_dir)
                all_model_dirs = []
                for d in sorted(Path(sparse_parent).iterdir()):
                    if not d.is_dir() or d.name == "merged":
                        continue
                    ni, _ = colmap._count_model(str(d))
                    if ni >= 5:
                        all_model_dirs.append((str(d), ni))

                if len(all_model_dirs) > 1:
                    _notify(PipelineStage.DENSE_RECONSTRUCTION, 0.0,
                            f"Running dense on {len(all_model_dirs)} sub-models...")
                    dense_ply, num_dense_points, best_dense_dir = self._multi_model_dense(
                        colmap, frames_dir, colmap_workspace, output_dir,
                        all_model_dirs, config.dense_max_image_size, _notify,
                    )
                else:
                    _notify(PipelineStage.DENSE_RECONSTRUCTION, 0.0,
                            "Starting dense reconstruction...")
                    dense_result = colmap.reconstruct_dense(
                        image_dir=frames_dir,
                        sparse_dir=active_sparse_dir,
                        workspace=colmap_workspace,
                        max_image_size=config.dense_max_image_size,
                    )
                    if dense_result.success:
                        import shutil
                        output_dense_ply = os.path.join(output_dir, "dense.ply")
                        shutil.copy2(dense_result.fused_ply, output_dense_ply)
                        dense_ply = output_dense_ply
                        num_dense_points = dense_result.num_points
                        best_dense_dir = dense_result.dense_dir

                if dense_ply and num_dense_points > 0:
                    dense_stage.status = "completed"
                    dense_stage.message = f"Dense: {num_dense_points:,} points"
                else:
                    dense_stage.status = "failed"
                    dense_stage.message = "Dense reconstruction produced no points"
                    log.warning("Dense reconstruction failed, continuing with sparse only")

                dense_stage.progress = 1.0
                dense_stage.elapsed_sec = _elapsed()
                _notify(PipelineStage.DENSE_RECONSTRUCTION, 1.0, dense_stage.message)
            else:
                stages.append(StageStatus(
                    stage=PipelineStage.DENSE_RECONSTRUCTION, status="skipped",
                    progress=1.0, message="Dense reconstruction disabled",
                ))

            # === Stage 6: Mesh Generation ===
            mesh_ply = None
            if config.enable_mesh and dense_ply and best_dense_dir:
                mesh_stage = StageStatus(stage=PipelineStage.MESH_GENERATION, status="running")
                stages.append(mesh_stage)
                _notify(PipelineStage.MESH_GENERATION, 0.0, "Generating mesh...")

                try:
                    mesh_output = os.path.join(output_dir, "mesh.ply")
                    fused_for_mesh = os.path.join(best_dense_dir, "fused.ply")
                    if not os.path.isfile(fused_for_mesh):
                        fused_for_mesh = dense_ply
                    colmap.generate_mesh(
                        dense_dir=best_dense_dir,
                        fused_ply=fused_for_mesh,
                        output_path=mesh_output,
                        method=config.mesh_method,
                    )
                    mesh_ply = mesh_output
                    mesh_stage.status = "completed"
                    mesh_stage.message = f"Mesh: {mesh_output}"
                except Exception as e:
                    mesh_stage.status = "failed"
                    mesh_stage.message = f"Mesh failed: {e}"
                    log.warning("Mesh generation failed: %s", e)

                mesh_stage.progress = 1.0
                mesh_stage.elapsed_sec = _elapsed()
                _notify(PipelineStage.MESH_GENERATION, 1.0, mesh_stage.message)
            else:
                stages.append(StageStatus(
                    stage=PipelineStage.MESH_GENERATION, status="skipped",
                    progress=1.0, message="Mesh generation skipped",
                ))

            # === Done ===
            total_elapsed = _elapsed()
            log.info(
                "Pipeline complete in %.1f sec: %d images -> %d sparse / %d dense points",
                total_elapsed, sparse_result.num_images,
                sparse_result.num_points, num_dense_points,
            )

            return PipelineResult(
                project_id=project_id,
                success=True,
                output_dir=output_dir,
                stages=stages,
                sparse_ply=sparse_ply,
                dense_ply=dense_ply,
                mesh_ply=mesh_ply,
                num_images=sparse_result.num_images,
                num_sparse_points=sparse_result.num_points,
                num_dense_points=num_dense_points,
                total_elapsed_sec=total_elapsed,
            )

        except Exception as e:
            total_elapsed = _elapsed()
            log.error("Pipeline failed after %.1f sec: %s", total_elapsed, e)

            for s in stages:
                if s.status == "running":
                    s.status = "failed"
                    s.message = str(e)

            return PipelineResult(
                project_id=project_id,
                success=False,
                output_dir=output_dir,
                stages=stages,
                error=str(e),
                total_elapsed_sec=total_elapsed,
            )

    @staticmethod
    def _extract_frames(config: PipelineConfig, frames_dir: str) -> list[str]:
        """Extract frames from video or image directory."""
        from spatial.ingest.video_extractor import VideoExtractor

        input_path = os.path.abspath(config.input_path)
        extractor = VideoExtractor()

        if os.path.isfile(input_path):
            extraction = extractor.extract_frames(
                video_path=input_path,
                output_dir=frames_dir,
                fps=config.fps,
                strategy=config.strategy,
                max_frames=config.max_frames,
                max_image_size=config.max_image_size,
            )
        elif os.path.isdir(input_path):
            extraction = extractor.extract_frames_from_images(
                image_dir=input_path,
                output_dir=frames_dir,
                max_image_size=config.max_image_size,
            )
        else:
            raise FileNotFoundError(f"Input not found: {input_path}")

        return extraction.frames

    @staticmethod
    def _multi_model_dense(
        colmap,
        frames_dir: str,
        colmap_workspace: str,
        output_dir: str,
        model_dirs: list[tuple[str, int]],
        max_image_size: int,
        _notify,
    ) -> tuple[str | None, int, str | None]:
        """
        Run dense reconstruction on all qualifying sub-models and merge.

        Returns:
            (combined_ply_path, total_points, best_dense_dir)
        """
        import numpy as np

        try:
            import open3d as o3d
        except ImportError:
            log.warning("Open3D not available, falling back to single-model dense")
            return None, 0, None

        all_points = []
        all_colors = []
        all_normals = []
        best_dense_dir = None
        best_count = 0

        for i, (model_dir, num_images) in enumerate(model_dirs):
            model_name = os.path.basename(model_dir)
            dense_ws = os.path.join(colmap_workspace, f"dense_{model_name}")
            progress = i / len(model_dirs)
            _notify(
                PipelineStage.DENSE_RECONSTRUCTION, progress,
                f"Dense model {model_name} ({num_images} imgs, {i+1}/{len(model_dirs)})...",
            )

            result = colmap.reconstruct_dense(
                image_dir=frames_dir,
                sparse_dir=model_dir,
                workspace=dense_ws,
                max_image_size=max_image_size,
            )

            if not result.success or result.num_points == 0:
                log.warning("Dense model %s: failed or 0 points", model_name)
                continue

            log.info("Dense model %s: %d points", model_name, result.num_points)

            if result.num_points > best_count:
                best_count = result.num_points
                best_dense_dir = result.dense_dir

            pcd = o3d.io.read_point_cloud(result.fused_ply)
            if len(pcd.points) > 0:
                all_points.append(np.asarray(pcd.points))
                if pcd.has_colors():
                    all_colors.append(np.asarray(pcd.colors))
                if pcd.has_normals():
                    all_normals.append(np.asarray(pcd.normals))

        if not all_points:
            return None, 0, None

        # Combine all point clouds
        combined = o3d.geometry.PointCloud()
        combined.points = o3d.utility.Vector3dVector(np.vstack(all_points))
        if all_colors and len(all_colors) == len(all_points):
            combined.colors = o3d.utility.Vector3dVector(np.vstack(all_colors))
        if all_normals and len(all_normals) == len(all_points):
            combined.normals = o3d.utility.Vector3dVector(np.vstack(all_normals))

        combined_path = os.path.join(output_dir, "dense.ply")
        o3d.io.write_point_cloud(combined_path, combined)
        total_points = len(combined.points)

        log.info(
            "Combined %d sub-models -> %d points",
            len(all_points), total_points,
        )

        return combined_path, total_points, best_dense_dir
