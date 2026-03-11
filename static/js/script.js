// # 1. Main Initialization
document.addEventListener("DOMContentLoaded", () => {
    // 1.1 Core UI (Safe Mode / Filters)
    initCoreUI();

    // 1.2 Gallery Features (Lightbox / Info)
    initGalleryFeatures();

    // 1.3 Bulk Operations (Selection / Delete / Ghosting)
    initBulkActions();

    // 1.4 Album Specific Features (Reordering / Suggestions)
    initAlbumFeatures();

    // 1.5 Infinite Scroll
    initInfiniteScroll();
});

// # 2. Core UI Functions
function initCoreUI() {
    // 2.1 Safe Mode Toggle
    const safeToggle = document.getElementById("safe-mode-checkbox");
    if (safeToggle) {
        safeToggle.addEventListener("change", () => {
            const value = safeToggle.checked ? "on" : "off";
            document.cookie = `safe_mode=${value};path=/;max-age=2592000;samesite=Lax`;
            window.location.reload();
        });
    }

    // 2.2 Media Filter Buttons
    const filterGroup = document.getElementById("media-filter");
    if (filterGroup) {
        filterGroup.addEventListener("click", (e) => {
            const btn = e.target.closest(".media-filter-button");
            if (!btn) return;
            document.cookie = `media_filter=${btn.dataset.filter};path=/;max-age=2592000;samesite=Lax`;
            window.location.reload();
        });
    }
}

// # 3. Gallery Features (Lightboxes)
function initGalleryFeatures() {
    const gallery = document.querySelector(".gallery-grid") || document.body;
    
    gallery.addEventListener("click", (e) => {
        if (document.body.classList.contains("selection-mode-active")) return;

        const infoIcon = e.target.closest(".info-icon");
        const galleryLink = e.target.closest(".gallery-link");

        // 3.1 Metadata Info Lightbox
        if (infoIcon) {
            e.preventDefault();
            const d = infoIcon.dataset;
            const content = `
                <div class="info-lightbox-content">
                    <h3>${d.filename}</h3>
                    <dl>
                        <dt>Sampler</dt><dd>${d.sampler || "N/A"}</dd>
                        <dt>Steps</dt><dd>${d.steps || "N/A"}</dd>
                        <dt>CFG</dt><dd>${d.cfg || "N/A"}</dd>
                        ${d.prompt ? `<dt>Prompt</dt><dd class="prompt">${d.prompt}</dd>` : ""}
                    </dl>
                </div>`;
            basicLightbox.create(content).show();
            return;
        }

        // 3.2 Full Image Lightbox (CORRECTED WITH SIZE CONSTRAINTS)
        if (galleryLink) {
            e.preventDefault();
            const isVideo = galleryLink.dataset.isVideo === "true";
            const mediaUrl = galleryLink.dataset.fullImageUrl;
            
            // 3.2.1 Added explicit style constraints to prevent overflow
            const mediaStyle = `style="max-width: 95vw; max-height: 82vh; display: block; object-fit: contain;"`;
            
            const mediaHtml = isVideo 
                ? `<video controls autoplay loop muted ${mediaStyle}><source src="${mediaUrl}" type="${galleryLink.dataset.videoType}"></video>`
                : `<img src="${mediaUrl}" ${mediaStyle}>`;
            
            const content = `
                <div class="image-lightbox-container">
                    ${mediaHtml}
                    <div class="lightbox-caption">
                        <span class="lightbox-filename">${galleryLink.querySelector(".filename").textContent}</span>
                        <a href="${galleryLink.href}" class="lightbox-details-button">Details & Actions</a>
                    </div>
                </div>`;
            
            basicLightbox.create(content).show();
        }
    });
}

// # 4. Bulk Operations (The "Ghosting" Deletion Logic)
function initBulkActions() {
    const selectBtn = document.getElementById("select-mode-button");
    const bulkPanel = document.getElementById("bulk-actions-panel");
    const bulkDeleteBtn = document.getElementById("bulk-delete-btn") || document.getElementById("bulk-action-delete");
    const bulkAlbumBtn = document.getElementById("bulk-action-add-to-album");
    const apiUrl = document.body.dataset.apiBulkUrl;

    let selectedIds = new Set();
    let isMode = false;

    if (!selectBtn) return;

    // 4.1 Toggle Mode
    selectBtn.addEventListener("click", () => {
        isMode = !isMode;
        document.body.classList.toggle("selection-mode-active", isMode);
        selectBtn.textContent = isMode ? "Cancel" : "Select";
        if (!isMode) {
            selectedIds.clear();
            document.querySelectorAll(".gallery-item.selected").forEach(el => el.classList.remove("selected"));
            bulkPanel.classList.remove("visible");
        }
    });

    // 4.2 Click Handling (Event Delegation)
    document.addEventListener("click", (e) => {
        if (!isMode) return;
        const item = e.target.closest(".gallery-item");
        if (!item || item.classList.contains("is-deleted")) return;

        e.preventDefault();
        const id = parseInt(item.dataset.id);
        if (selectedIds.has(id)) {
            selectedIds.delete(id);
            item.classList.remove("selected");
        } else {
            selectedIds.add(id);
            item.classList.add("selected");
        }

        const count = selectedIds.size;
        document.getElementById("selected-count").textContent = count;
        bulkPanel.classList.toggle("visible", count > 0);
    });

    // 4.3 API Action Runner (Handles Ghosting)
    async function runBulkAction(action, value = null) {
        const ids = Array.from(selectedIds);
        try {
            const resp = await fetch(apiUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image_ids: ids, action, value })
            });
            
            if (!resp.ok) throw new Error("API Error");

            if (action === "delete") {
                // 4.3.1 THE GHOSTING FIX: Replace content instead of reordering
                ids.forEach(id => {
                    const el = document.querySelector(`.gallery-item[data-id="${id}"]`);
                    if (el) {
                        el.classList.add("is-deleted");
                        el.classList.remove("selected");
                        el.innerHTML = '<div class="deleted-msg">Deleted</div>';
                    }
                });
                selectedIds.clear();
                bulkPanel.classList.remove("visible");
            } else {
                window.location.reload();
            }
        } catch (err) { alert("Action failed: " + err.message); }
    }

    if (bulkDeleteBtn) bulkDeleteBtn.addEventListener("click", () => {
        if (confirm(`Delete ${selectedIds.size} images?`)) runBulkAction("delete");
    });

    if (bulkAlbumBtn) bulkAlbumBtn.addEventListener("click", () => {
        const albumId = document.getElementById("bulk-add-to-album").value;
        runBulkAction("add_to_album", albumId === "null" ? null : parseInt(albumId));
    });if (bulkAlbumBtn) {
    bulkAlbumBtn.addEventListener("click", () => {
        const albumSelect = document.getElementById("bulk-add-to-album");
        const rawValue = albumSelect.value;
        
        let finalValue;
        if (rawValue === "null" || rawValue === "") {
            finalValue = null;
        } else {
            finalValue = parseInt(rawValue, 10);
        }

        if (confirm(`Move ${selectedIds.size} images to selected album?`)) {
            runBulkAction("add_to_album", finalValue);
        }
    });
}
}

// # 5. Album Specific Features
function initAlbumFeatures() {
    const reorderBtn = document.getElementById("reorder-button");
    const analyzeBtn = document.getElementById("analyze-button");
    const gridContainer = document.getElementById("album-grid-sortable");
    const albumBaseUrl = document.body.dataset.apiAlbumUrl;

    if (!gridContainer) return;
    const albumId = gridContainer.dataset.albumId;

    // 5.1 SortableJS Reordering
    let sortable = null;
    if (reorderBtn) {
        reorderBtn.addEventListener("click", () => {
            if (sortable) {
                sortable.destroy();
                sortable = null;
                reorderBtn.textContent = "Reorder Images";
                gridContainer.classList.remove("reordering-active");
            } else {
                const list = gridContainer.querySelector(".gallery-grid");
                sortable = new Sortable(list, {
                    animation: 150,
                    ghostClass: "sortable-ghost",
                    onEnd: async () => {
                        const ids = Array.from(list.querySelectorAll(".gallery-item")).map(el => parseInt(el.dataset.id));
                        await fetch(`${albumBaseUrl}/${albumId}/reorder`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ image_ids: ids })
                        });
                    }
                });
                gridContainer.classList.add("reordering-active");
                reorderBtn.textContent = "Finish Reordering";
            }
        });
    }

    // 5.2 Creative Director Suggestions
    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", async () => {
            const grid = document.getElementById("suggestions-grid");
            const container = document.getElementById("suggestions-container");
            container.style.display = "block";
            
            const resp = await fetch(`${albumBaseUrl}/${albumId}/suggestions`);
            const images = await resp.json();
            
            grid.innerHTML = images.map(img => `
                <div class="gallery-item" data-id="${img.id}">
                    <a href="/image/${img.id}">
                        <img src="/uploads/${img.thumbnail_path}" loading="lazy">
                    </a>
                </div>`).join("");
        });
    }
}

// # 6. Infinite Scroll Logic
function initInfiniteScroll() {
    const trigger = document.getElementById("infinite-scroll-trigger");
    const galleryGrid = document.querySelector("#main-gallery-container .gallery-grid");
    if (!trigger || !galleryGrid) return;

    let skip = 50;
    let isLoading = false;

    const observer = new IntersectionObserver(async (entries) => {
        if (entries[0].isIntersecting && !isLoading) {
            isLoading = true;
            const resp = await fetch(`/gallery-chunk?skip=${skip}&limit=50`);
            const html = await resp.text();
            
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const newItems = doc.querySelectorAll(".gallery-item");
            
            if (newItems.length > 0) {
                newItems.forEach(item => galleryGrid.appendChild(item));
                skip += 50;
                isLoading = false;
            } else {
                trigger.innerHTML = "No more images.";
            }
        }
    }, { rootMargin: "200px" });

    observer.observe(trigger);
}