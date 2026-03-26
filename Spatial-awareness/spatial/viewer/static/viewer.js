import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';

// ─── State ───────────────────────────────────────────────────────────────────

const state = {
    scene: null,
    camera: null,
    renderer: null,
    controls: null,
    gridHelper: null,
    axesHelper: null,
    currentModel: null,
    pointSize: 2.0,
    bgMode: 'dark',
    showGrid: true,
    showAxes: true,
    colors: {
        dark: { bg: 0x1a1a2e, grid: 0x333355 },
        light: { bg: 0xe8e8e8, grid: 0xbbbbbb },
    },
};

// ─── Initialization ──────────────────────────────────────────────────────────

function init() {
    const canvas = document.getElementById('viewer-canvas');
    const container = document.getElementById('viewer-container');

    // Renderer
    state.renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        antialias: true,
        alpha: false,
    });
    state.renderer.setPixelRatio(window.devicePixelRatio);
    state.renderer.setSize(container.clientWidth, container.clientHeight);
    state.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // Scene
    state.scene = new THREE.Scene();
    state.scene.background = new THREE.Color(state.colors.dark.bg);

    // Camera
    state.camera = new THREE.PerspectiveCamera(
        60,
        container.clientWidth / container.clientHeight,
        0.01,
        10000
    );
    state.camera.position.set(5, 5, 5);
    state.camera.lookAt(0, 0, 0);

    // Controls
    state.controls = new OrbitControls(state.camera, state.renderer.domElement);
    state.controls.enableDamping = true;
    state.controls.dampingFactor = 0.1;
    state.controls.screenSpacePanning = true;
    state.controls.minDistance = 0.1;
    state.controls.maxDistance = 5000;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    state.scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(10, 10, 10);
    state.scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.3);
    dirLight2.position.set(-10, 5, -5);
    state.scene.add(dirLight2);

    // Grid
    state.gridHelper = new THREE.GridHelper(20, 40, state.colors.dark.grid, state.colors.dark.grid);
    state.gridHelper.material.opacity = 0.3;
    state.gridHelper.material.transparent = true;
    state.scene.add(state.gridHelper);

    // Axes
    state.axesHelper = new THREE.AxesHelper(3);
    state.scene.add(state.axesHelper);

    // Resize handler
    window.addEventListener('resize', onResize);

    // Start render loop
    animate();

    // Setup UI handlers
    setupUI();

    // Setup drag and drop
    setupDragDrop();

    // Load projects list
    loadProjects();

    // Check URL for file parameter
    const params = new URLSearchParams(window.location.search);
    const filePath = params.get('file');
    if (filePath) {
        loadFromServer(filePath);
    }
}

function onResize() {
    const container = document.getElementById('viewer-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    state.camera.aspect = width / height;
    state.camera.updateProjectionMatrix();
    state.renderer.setSize(width, height);
}

function animate() {
    requestAnimationFrame(animate);
    state.controls.update();
    state.renderer.render(state.scene, state.camera);
}

// ─── UI Setup ────────────────────────────────────────────────────────────────

function setupUI() {
    // Sidebar toggle
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarOpen = document.getElementById('sidebar-open');

    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        sidebarOpen.classList.add('visible');
        setTimeout(onResize, 310);
    });

    sidebarOpen.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        sidebarOpen.classList.remove('visible');
        setTimeout(onResize, 310);
    });

    // Point size slider
    const pointSlider = document.getElementById('point-size-slider');
    const pointValue = document.getElementById('point-size-value');
    pointSlider.addEventListener('input', () => {
        state.pointSize = parseFloat(pointSlider.value);
        pointValue.textContent = state.pointSize.toFixed(1);
        updatePointSize();
    });

    // Background toggle
    document.getElementById('bg-dark').addEventListener('click', () => {
        setBackground('dark');
    });
    document.getElementById('bg-light').addEventListener('click', () => {
        setBackground('light');
    });

    // Grid toggle
    document.getElementById('toggle-grid').addEventListener('click', (e) => {
        state.showGrid = !state.showGrid;
        state.gridHelper.visible = state.showGrid;
        e.target.classList.toggle('active', state.showGrid);
    });

    // Axes toggle
    document.getElementById('toggle-axes').addEventListener('click', (e) => {
        state.showAxes = !state.showAxes;
        state.axesHelper.visible = state.showAxes;
        e.target.classList.toggle('active', state.showAxes);
    });

    // Reset camera
    document.getElementById('btn-reset-camera').addEventListener('click', resetCamera);

    // Fit to view
    document.getElementById('btn-fit-view').addEventListener('click', fitToView);

    // Refresh projects
    document.getElementById('refresh-projects').addEventListener('click', loadProjects);
}

function setBackground(mode) {
    state.bgMode = mode;
    const colors = state.colors[mode];
    state.scene.background = new THREE.Color(colors.bg);

    state.gridHelper.material.color.setHex(colors.grid);

    document.getElementById('bg-dark').classList.toggle('active', mode === 'dark');
    document.getElementById('bg-light').classList.toggle('active', mode === 'light');
}

function updatePointSize() {
    if (!state.currentModel) return;

    state.currentModel.traverse((child) => {
        if (child.isPoints && child.material) {
            child.material.size = state.pointSize;
            child.material.needsUpdate = true;
        }
    });
}

function resetCamera() {
    state.camera.position.set(5, 5, 5);
    state.camera.lookAt(0, 0, 0);
    state.controls.target.set(0, 0, 0);
    state.controls.update();
}

function fitToView() {
    if (!state.currentModel) return;

    const box = new THREE.Box3().setFromObject(state.currentModel);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);

    if (maxDim === 0) return;

    const fov = state.camera.fov * (Math.PI / 180);
    let cameraDistance = maxDim / (2 * Math.tan(fov / 2));
    cameraDistance *= 1.5;

    const direction = new THREE.Vector3(1, 0.8, 1).normalize();
    state.camera.position.copy(center).add(direction.multiplyScalar(cameraDistance));
    state.controls.target.copy(center);
    state.controls.update();

    state.camera.near = maxDim * 0.001;
    state.camera.far = maxDim * 100;
    state.camera.updateProjectionMatrix();
}

// ─── Drag & Drop ─────────────────────────────────────────────────────────────

function setupDragDrop() {
    const container = document.getElementById('viewer-container');
    const dropZone = document.getElementById('drop-zone');
    let dragCounter = 0;

    container.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        dropZone.classList.remove('hidden');
    });

    container.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            dropZone.classList.add('hidden');
        }
    });

    container.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    container.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dropZone.classList.add('hidden');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.name.toLowerCase().endsWith('.ply')) {
                loadLocalFile(file);
            } else {
                showError('Only PLY files are supported for drag & drop.');
            }
        }
    });
}

// ─── File Loading ────────────────────────────────────────────────────────────

function showLoading(message) {
    const overlay = document.getElementById('loading-overlay');
    const text = document.getElementById('loading-text');
    text.textContent = message || 'Loading...';
    overlay.classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.add('hidden');
}

function showError(message) {
    hideLoading();
    console.error(message);
    updateStat('stat-status', 'Error');
    const filenameDisplay = document.getElementById('filename-display');
    filenameDisplay.textContent = 'Error: ' + message;
    filenameDisplay.style.color = '#ff6b6b';
    setTimeout(() => {
        filenameDisplay.style.color = '';
    }, 5000);
}

function clearCurrentModel() {
    if (state.currentModel) {
        state.scene.remove(state.currentModel);
        state.currentModel.traverse((child) => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach((m) => m.dispose());
                } else {
                    child.material.dispose();
                }
            }
        });
        state.currentModel = null;
    }
}

function loadLocalFile(file) {
    showLoading(`Loading ${file.name}...`);

    const reader = new FileReader();
    reader.onload = (e) => {
        const buffer = e.target.result;
        parsePLY(buffer, file.name, file.size);
    };
    reader.onerror = () => {
        showError('Failed to read file.');
    };
    reader.readAsArrayBuffer(file);
}

function loadFromServer(filePath) {
    const url = `/api/files/${filePath}`;
    showLoading(`Loading ${filePath}...`);

    fetch(url)
        .then((resp) => {
            if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
            return resp.arrayBuffer();
        })
        .then((buffer) => {
            const filename = filePath.split('/').pop();
            parsePLY(buffer, filename, buffer.byteLength);
        })
        .catch((err) => {
            showError(`Failed to load file: ${err.message}`);
        });
}

function parsePLY(buffer, filename, fileSize) {
    const loader = new PLYLoader();

    try {
        const geometry = loader.parse(buffer);

        clearCurrentModel();

        geometry.computeBoundingBox();
        const bbox = geometry.boundingBox;
        const center = bbox.getCenter(new THREE.Vector3());
        const size = bbox.getSize(new THREE.Vector3());

        const hasColors = geometry.hasAttribute('color');
        const hasNormals = geometry.hasAttribute('normal');
        const vertexCount = geometry.getAttribute('position').count;
        const indexCount = geometry.index ? geometry.index.count : 0;
        const faceCount = Math.floor(indexCount / 3);
        const isMesh = faceCount > 0;

        let object;

        if (isMesh) {
            if (!hasNormals) {
                geometry.computeVertexNormals();
            }

            let material;
            if (hasColors) {
                material = new THREE.MeshStandardMaterial({
                    vertexColors: true,
                    metalness: 0.1,
                    roughness: 0.8,
                    side: THREE.DoubleSide,
                });
            } else {
                material = new THREE.MeshStandardMaterial({
                    color: 0x6699cc,
                    metalness: 0.1,
                    roughness: 0.8,
                    side: THREE.DoubleSide,
                });
            }

            object = new THREE.Mesh(geometry, material);
        } else {
            let material;
            if (hasColors) {
                material = new THREE.PointsMaterial({
                    size: state.pointSize,
                    vertexColors: true,
                    sizeAttenuation: true,
                });
            } else {
                material = new THREE.PointsMaterial({
                    size: state.pointSize,
                    color: 0x6699cc,
                    sizeAttenuation: true,
                });
            }

            object = new THREE.Points(geometry, material);
        }

        // Center the model at origin
        object.position.sub(center);

        const group = new THREE.Group();
        group.add(object);
        state.currentModel = group;
        state.scene.add(group);

        // Update grid scale based on model size
        const maxDim = Math.max(size.x, size.y, size.z);
        if (maxDim > 0) {
            const gridSize = Math.max(20, Math.ceil(maxDim * 2));
            state.scene.remove(state.gridHelper);
            const gridColor = state.colors[state.bgMode].grid;
            state.gridHelper = new THREE.GridHelper(gridSize, 40, gridColor, gridColor);
            state.gridHelper.material.opacity = 0.3;
            state.gridHelper.material.transparent = true;
            state.gridHelper.visible = state.showGrid;
            state.scene.add(state.gridHelper);

            // Update axes scale
            state.scene.remove(state.axesHelper);
            state.axesHelper = new THREE.AxesHelper(maxDim * 0.3);
            state.axesHelper.visible = state.showAxes;
            state.scene.add(state.axesHelper);
        }

        // Update stats
        updateStat('stat-status', 'Loaded');
        updateStat('stat-type', isMesh ? 'Triangle Mesh' : 'Point Cloud');
        updateStat('stat-vertices', vertexCount.toLocaleString());
        updateStat('stat-faces', isMesh ? faceCount.toLocaleString() : '-');
        updateStat('stat-colors', hasColors ? 'Yes' : 'No');
        updateStat(
            'stat-bbox',
            `${size.x.toFixed(2)} x ${size.y.toFixed(2)} x ${size.z.toFixed(2)}`
        );
        updateStat('stat-filesize', formatFileSize(fileSize));

        document.getElementById('filename-display').textContent = filename;

        fitToView();
        hideLoading();
    } catch (err) {
        showError(`Failed to parse PLY: ${err.message}`);
    }
}

function updateStat(elementId, value) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = value;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ─── Projects ────────────────────────────────────────────────────────────────

async function loadProjects() {
    const listEl = document.getElementById('projects-list');
    listEl.innerHTML = '<div class="loading-indicator">Loading projects...</div>';

    try {
        const resp = await fetch('/api/projects');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (data.projects.length === 0) {
            listEl.innerHTML = '<div class="empty-state">No projects found.<br><span class="hint">Add PLY files to data/projects/</span></div>';
            return;
        }

        listEl.innerHTML = '';
        for (const project of data.projects) {
            const projectEl = createProjectElement(project);
            listEl.appendChild(projectEl);
        }
    } catch (err) {
        listEl.innerHTML = `<div class="empty-state">Failed to load projects.<br><span class="hint">${err.message}</span></div>`;
    }
}

function createProjectElement(project) {
    const div = document.createElement('div');
    div.className = 'project-item';

    const header = document.createElement('div');
    header.className = 'project-header';
    header.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="project-chevron">
            <polyline points="9 18 15 12 9 6"/>
        </svg>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <span class="project-name">${project.id}</span>
        <span class="file-count">${project.ply_count} PLY</span>
    `;

    const filesList = document.createElement('div');
    filesList.className = 'project-files hidden';

    let filesLoaded = false;

    header.addEventListener('click', async () => {
        const isExpanded = !filesList.classList.contains('hidden');
        if (isExpanded) {
            filesList.classList.add('hidden');
            div.classList.remove('expanded');
        } else {
            if (!filesLoaded) {
                filesList.innerHTML = '<div class="loading-indicator small">Loading files...</div>';
                try {
                    const resp = await fetch(`/api/projects/${project.id}/files`);
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    const data = await resp.json();

                    filesList.innerHTML = '';
                    if (data.files.length === 0) {
                        filesList.innerHTML = '<div class="empty-state small">No 3D files found</div>';
                    } else {
                        for (const file of data.files) {
                            const fileEl = createFileElement(file);
                            filesList.appendChild(fileEl);
                        }
                    }
                    filesLoaded = true;
                } catch (err) {
                    filesList.innerHTML = `<div class="empty-state small">Error: ${err.message}</div>`;
                }
            }
            filesList.classList.remove('hidden');
            div.classList.add('expanded');
        }
    });

    div.appendChild(header);
    div.appendChild(filesList);
    return div;
}

function createFileElement(file) {
    const div = document.createElement('div');
    div.className = 'file-item';

    const icon = file.extension === '.ply'
        ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>';

    div.innerHTML = `
        ${icon}
        <span class="file-name">${file.name}</span>
        <span class="file-size">${file.size_mb} MB</span>
    `;

    div.addEventListener('click', () => {
        loadFromServer(file.path);

        // Highlight active file
        document.querySelectorAll('.file-item.active').forEach((el) => {
            el.classList.remove('active');
        });
        div.classList.add('active');
    });

    return div;
}

// ─── Start ───────────────────────────────────────────────────────────────────

init();
