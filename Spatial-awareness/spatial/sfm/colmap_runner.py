"""COLMAP subprocess wrapper for Structure from Motion."""

import os
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from spatial.utils.logging_config import get_logger
from spatial.utils.platform_compat import find_binary
from spatial.utils.gpu import check_cuda_available

log = get_logger("sfm.colmap")


@dataclass
class SparseResult:
    """Result of sparse reconstruction."""
    workspace: str
    sparse_dir: str          # Path to sparse/0/
    num_images: int
    num_points: int
    cameras_file: str
    images_file: str
    points3d_file: str
    success: bool
    num_models: int = 1
    error: str | None = None


@dataclass
class DenseResult:
    """Result of dense reconstruction."""
    workspace: str
    dense_dir: str           # Path to dense workspace
    fused_ply: str           # Path to fused.ply
    num_points: int
    success: bool
    mesh_ply: str | None = None  # Path to meshed output
    error: str | None = None


@dataclass
class ColmapConfig:
    """COLMAP reconstruction configuration."""
    use_gpu: bool = True
    sift_max_features: int = 16384
    matcher: str = "exhaustive"  # "exhaustive" or "sequential"
    ba_refine_focal_length: bool = True
    ba_refine_extra_params: bool = True
    min_num_matches: int = 10
    max_image_size: int = 3200
    # SIFT tuning for feature-poor scenes (walls, floors)
    sift_peak_threshold: float = 0.004  # lower = more features (default 0.00667)
    sift_edge_threshold: float = 16     # higher = keep more edge features (default 10)


class ColmapRunner:
    """Wrapper around COLMAP binary for SfM reconstruction."""

    def __init__(
        self,
        colmap_path: str | None = None,
        config: ColmapConfig | None = None,
    ):
        self.colmap = colmap_path or find_binary("colmap", "COLMAP_PATH")
        if not self.colmap:
            raise FileNotFoundError(
                "COLMAP not found. Run 'python scripts/install_colmap.py' to install, "
                "or set COLMAP_PATH environment variable."
            )
        self.config = config or ColmapConfig()

        # Auto-disable GPU if CUDA not available
        if self.config.use_gpu and not check_cuda_available():
            log.warning("CUDA not available, falling back to CPU for COLMAP")
            self.config.use_gpu = False

        self._verify_colmap()

    def _verify_colmap(self):
        """Verify COLMAP binary is accessible."""
        try:
            result = subprocess.run(
                [self.colmap, "help"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode not in (0, 1):  # COLMAP help returns 1 on some versions
                raise RuntimeError(f"COLMAP verification failed: {result.stderr}")
            log.info("COLMAP binary verified: %s", self.colmap)
        except FileNotFoundError:
            raise FileNotFoundError(f"COLMAP not found at: {self.colmap}")

    def _run_colmap(self, command: str, args: dict, timeout: int = 3600) -> str:
        """Run a COLMAP command with arguments."""
        cmd = [self.colmap, command]
        for key, value in args.items():
            cmd.append(f"--{key}")
            cmd.append(str(value))

        log.info("Running: colmap %s", command)
        log.debug("Full command: %s", " ".join(cmd))

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )

        if result.returncode != 0:
            error_msg = result.stderr[-1000:] if result.stderr else "Unknown error"
            log.error("COLMAP %s failed: %s", command, error_msg)
            raise RuntimeError(f"COLMAP {command} failed: {error_msg}")

        # COLMAP 4.x logs to stderr; combine both streams for parsing
        return result.stdout + "\n" + result.stderr

    def reconstruct_sparse(
        self,
        image_dir: str,
        workspace: str,
    ) -> SparseResult:
        """
        Run full sparse reconstruction pipeline.

        Args:
            image_dir: Directory containing input images.
            workspace: Working directory for COLMAP database and output.

        Returns:
            SparseResult with reconstruction details.
        """
        image_dir = os.path.abspath(image_dir)
        workspace = os.path.abspath(workspace)
        os.makedirs(workspace, exist_ok=True)

        database_path = os.path.join(workspace, "database.db")
        sparse_dir = os.path.join(workspace, "sparse")
        os.makedirs(sparse_dir, exist_ok=True)

        try:
            # Step 1: Feature extraction
            self._feature_extract(image_dir, database_path)

            # Step 2: Feature matching
            self._feature_match(database_path)

            # Step 3: Sparse reconstruction (mapper)
            self._sparse_mapper(database_path, image_dir, sparse_dir)

            # Check results — find the best model (most registered images)
            model_dirs = sorted(
                d for d in Path(sparse_dir).iterdir() if d.is_dir()
            )
            if not model_dirs:
                return SparseResult(
                    workspace=workspace,
                    sparse_dir=sparse_dir,
                    num_images=0,
                    num_points=0,
                    cameras_file="",
                    images_file="",
                    points3d_file="",
                    success=False,
                    error="No reconstruction produced. Try with more images or different angles.",
                )

            # Pick model with most registered images
            best_dir = None
            best_images = 0
            best_points = 0
            for d in model_dirs:
                ni, np_ = self._count_model(str(d))
                log.info("  Model %s: %d images, %d points", d.name, ni, np_)
                if ni > best_images:
                    best_dir = str(d)
                    best_images = ni
                    best_points = np_

            model_dir = best_dir
            num_images, num_points = best_images, best_points
            log.info(
                "Selected best model: %s (%d images, %d points, %d total models)",
                os.path.basename(model_dir), num_images, num_points, len(model_dirs),
            )

            log.info(
                "Sparse reconstruction complete: %d images, %d points",
                num_images, num_points,
            )

            return SparseResult(
                workspace=workspace,
                sparse_dir=model_dir,
                num_images=num_images,
                num_points=num_points,
                cameras_file=os.path.join(model_dir, "cameras.bin"),
                images_file=os.path.join(model_dir, "images.bin"),
                points3d_file=os.path.join(model_dir, "points3D.bin"),
                success=True,
                num_models=len(model_dirs),
            )

        except Exception as e:
            log.error("Sparse reconstruction failed: %s", e)
            return SparseResult(
                workspace=workspace,
                sparse_dir=sparse_dir,
                num_images=0,
                num_points=0,
                cameras_file="",
                images_file="",
                points3d_file="",
                success=False,
                error=str(e),
            )

    def _feature_extract(self, image_dir: str, database_path: str):
        """Extract SIFT features from images."""
        gpu_str = "1" if self.config.use_gpu else "0"
        self._run_colmap("feature_extractor", {
            "database_path": database_path,
            "image_path": image_dir,
            "ImageReader.single_camera": "1",
            "ImageReader.camera_model": "OPENCV",
            "FeatureExtraction.use_gpu": gpu_str,
            "FeatureExtraction.max_image_size": str(self.config.max_image_size),
            "SiftExtraction.max_num_features": str(self.config.sift_max_features),
            "SiftExtraction.peak_threshold": str(self.config.sift_peak_threshold),
            "SiftExtraction.edge_threshold": str(self.config.sift_edge_threshold),
        })
        log.info("Feature extraction complete")

    def _feature_match(self, database_path: str):
        """Match features between images."""
        gpu_str = "1" if self.config.use_gpu else "0"

        if self.config.matcher == "sequential":
            self._run_colmap("sequential_matcher", {
                "database_path": database_path,
                "FeatureMatching.use_gpu": gpu_str,
                "TwoViewGeometry.min_num_inliers": str(self.config.min_num_matches),
                "SequentialMatching.overlap": "10",
                "SequentialMatching.loop_detection": "1",
            })
        else:
            self._run_colmap("exhaustive_matcher", {
                "database_path": database_path,
                "FeatureMatching.use_gpu": gpu_str,
                "TwoViewGeometry.min_num_inliers": str(self.config.min_num_matches),
            })
        log.info("Feature matching complete (strategy=%s)", self.config.matcher)

    def _sparse_mapper(
        self, database_path: str, image_dir: str, sparse_dir: str,
    ):
        """Run incremental sparse mapper."""
        self._run_colmap("mapper", {
            "database_path": database_path,
            "image_path": image_dir,
            "output_path": sparse_dir,
            "Mapper.ba_refine_focal_length": "1" if self.config.ba_refine_focal_length else "0",
            "Mapper.ba_refine_extra_params": "1" if self.config.ba_refine_extra_params else "0",
        }, timeout=7200)
        log.info("Sparse mapping complete")

    def _count_model(self, model_dir: str) -> tuple[int, int]:
        """Count images and 3D points in a sparse model using model_analyzer."""
        try:
            output = self._run_colmap("model_analyzer", {
                "path": model_dir,
            }, timeout=30)

            num_images = 0
            num_points = 0
            for line in output.splitlines():
                if "Registered images:" in line:
                    num_images = int(line.split(":")[-1].strip())
                elif line.strip().endswith("Points:") or "] Points:" in line:
                    # COLMAP 4.x: "I2026... Points: 747"
                    num_points = int(line.split(":")[-1].strip())

            return num_images, num_points
        except Exception:
            # Fallback: count by file existence
            images_bin = os.path.join(model_dir, "images.bin")
            points_bin = os.path.join(model_dir, "points3D.bin")
            return (
                1 if os.path.isfile(images_bin) else 0,
                1 if os.path.isfile(points_bin) else 0,
            )

    def export_ply(self, sparse_dir: str, output_path: str) -> str:
        """Export sparse model to PLY format."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self._run_colmap("model_converter", {
            "input_path": sparse_dir,
            "output_path": output_path,
            "output_type": "PLY",
        }, timeout=120)
        log.info("Exported sparse model to PLY: %s", output_path)
        return output_path

    def export_txt(self, sparse_dir: str, output_dir: str) -> str:
        """Export sparse model to text format (for debugging)."""
        os.makedirs(output_dir, exist_ok=True)
        self._run_colmap("model_converter", {
            "input_path": sparse_dir,
            "output_path": output_dir,
            "output_type": "TXT",
        }, timeout=120)
        log.info("Exported sparse model to TXT: %s", output_dir)
        return output_dir

    def merge_models(self, sparse_dir: str) -> str | None:
        """
        Attempt to merge multiple sub-models in sparse_dir.

        Returns the path to the merged model, or None if merging is
        not possible (e.g., only one model exists).
        """
        model_dirs = sorted(
            d for d in Path(sparse_dir).iterdir() if d.is_dir()
        )
        if len(model_dirs) < 2:
            return None

        merged_dir = os.path.join(sparse_dir, "merged")
        os.makedirs(merged_dir, exist_ok=True)

        # Start with the largest model
        models_by_size = []
        for d in model_dirs:
            if d.name == "merged":
                continue
            ni, np_ = self._count_model(str(d))
            models_by_size.append((ni, str(d)))
        models_by_size.sort(reverse=True)

        if len(models_by_size) < 2:
            return None

        # Iteratively merge pairs
        current = models_by_size[0][1]
        shutil.copytree(current, merged_dir, dirs_exist_ok=True)

        merged_count = 1
        for _, other_dir in models_by_size[1:]:
            try:
                self._run_colmap("model_merger", {
                    "input_path1": merged_dir,
                    "input_path2": other_dir,
                    "output_path": merged_dir,
                }, timeout=300)
                merged_count += 1
                log.info("Merged model %s into combined (%d merged)", other_dir, merged_count)
            except RuntimeError as e:
                log.warning("Could not merge model %s: %s", other_dir, e)

        if merged_count > 1:
            ni, np_ = self._count_model(merged_dir)
            log.info("Merged model: %d images, %d points", ni, np_)
            return merged_dir

        # Merging failed, clean up
        shutil.rmtree(merged_dir, ignore_errors=True)
        return None

    def reconstruct_dense(
        self,
        image_dir: str,
        sparse_dir: str,
        workspace: str,
        max_image_size: int = 2000,
    ) -> DenseResult:
        """
        Run dense reconstruction: undistort → patch_match → stereo fusion.

        Args:
            image_dir: Directory containing original images.
            sparse_dir: Path to sparse model directory (e.g., sparse/1/).
            workspace: Working directory for dense output.
            max_image_size: Max image dimension for dense matching.

        Returns:
            DenseResult with fused point cloud path.
        """
        image_dir = os.path.abspath(image_dir)
        sparse_dir = os.path.abspath(sparse_dir)
        workspace = os.path.abspath(workspace)
        dense_dir = os.path.join(workspace, "dense")
        os.makedirs(dense_dir, exist_ok=True)

        try:
            # Step 1: Undistort images
            log.info("Undistorting images for dense reconstruction...")
            self._run_colmap("image_undistorter", {
                "image_path": image_dir,
                "input_path": sparse_dir,
                "output_path": dense_dir,
                "output_type": "COLMAP",
                "max_image_size": str(max_image_size),
            }, timeout=600)
            log.info("Image undistortion complete")

            # Step 2: Patch match stereo (depth estimation)
            log.info("Running patch match stereo (this may take a while)...")
            self._run_colmap("patch_match_stereo", {
                "workspace_path": dense_dir,
                "workspace_format": "COLMAP",
                "PatchMatchStereo.geom_consistency": "1",
                "PatchMatchStereo.num_iterations": "5",
                "PatchMatchStereo.max_image_size": str(max_image_size),
            }, timeout=7200)
            log.info("Patch match stereo complete")

            # Step 3: Stereo fusion (merge depth maps into point cloud)
            fused_ply = os.path.join(dense_dir, "fused.ply")
            log.info("Running stereo fusion...")
            self._run_colmap("stereo_fusion", {
                "workspace_path": dense_dir,
                "workspace_format": "COLMAP",
                "output_path": fused_ply,
                "output_type": "PLY",
                "StereoFusion.min_num_pixels": "3",
                "StereoFusion.max_reproj_error": "2",
            }, timeout=1800)
            log.info("Stereo fusion complete: %s", fused_ply)

            # Count points in fused PLY
            num_points = self._count_ply_points(fused_ply)

            return DenseResult(
                workspace=workspace,
                dense_dir=dense_dir,
                fused_ply=fused_ply,
                num_points=num_points,
                success=True,
            )

        except Exception as e:
            log.error("Dense reconstruction failed: %s", e)
            return DenseResult(
                workspace=workspace,
                dense_dir=dense_dir,
                fused_ply="",
                num_points=0,
                success=False,
                error=str(e),
            )

    def generate_mesh(
        self,
        dense_dir: str,
        fused_ply: str,
        output_path: str,
        method: str = "poisson",
    ) -> str:
        """
        Generate mesh from dense point cloud.

        Args:
            dense_dir: Dense workspace directory.
            fused_ply: Path to fused.ply from stereo fusion.
            output_path: Output mesh path (.ply).
            method: "poisson" or "delaunay".

        Returns:
            Path to output mesh file.
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if method == "poisson":
            self._run_colmap("poisson_mesher", {
                "input_path": fused_ply,
                "output_path": output_path,
                "PoissonMeshing.depth": "11",
                "PoissonMeshing.color": "1",
                "PoissonMeshing.trim": "10",
            }, timeout=1800)
        elif method == "delaunay":
            self._run_colmap("delaunay_mesher", {
                "input_path": dense_dir,
                "input_type": "dense",
                "output_path": output_path,
            }, timeout=1800)
        else:
            raise ValueError(f"Unknown mesh method: {method}")

        log.info("Mesh generated (%s): %s", method, output_path)
        return output_path

    @staticmethod
    def _count_ply_points(ply_path: str) -> int:
        """Count vertices in a PLY file from its header."""
        if not os.path.isfile(ply_path):
            return 0
        try:
            with open(ply_path, "rb") as f:
                for line in f:
                    line_str = line.decode("ascii", errors="ignore").strip()
                    if line_str.startswith("element vertex"):
                        return int(line_str.split()[-1])
                    if line_str == "end_header":
                        break
        except Exception:
            pass
        return 0
