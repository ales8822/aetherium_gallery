
// static/js/script.js

console.log("Aetherium Gallery script loaded.");

document.addEventListener("DOMContentLoaded", () => {
     // 1. Setup Infinite Scroll for the Gallery Index
    initInfiniteScroll();
    
    // 2. Setup Bulk Selection and Deletion
    // initBulkSelection();
});

function initInfiniteScroll() {
    const trigger = document.getElementById("infinite-scroll-trigger");
    // We target the first child of our container, which should be your actual CSS grid element (.grid, .gallery, etc.)
    const galleryContainer = document.querySelector("#main-gallery-container > div") || document.querySelector("#main-gallery-container");
    
    // If we aren't on the gallery page, stop here.
    if (!trigger || !galleryContainer) return;

    let skip = 50; // We already loaded the first 50 on initial page load
    const limit = 50;
    let isLoading = false;
    let hasMore = true;

    // Create the IntersectionObserver
    const observer = new IntersectionObserver(async (entries) => {
        // When the trigger div enters the viewport
        if (entries[0].isIntersecting && !isLoading && hasMore) {
            isLoading = true;

            try {
                // Fetch the next chunk of images from the backend
                const response = await fetch(`/gallery-chunk?skip=${skip}&limit=${limit}`);
                if (!response.ok) throw new Error("Network response was not ok");
                
                const html = await response.text();
                
                // Parse the returned HTML string into actual DOM nodes
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, "text/html");
                
                // Extract the elements. We assume the chunk is wrapped in your grid class.
                // We just want the child elements (the image cards)
                const newItemsContainer = doc.body.firstElementChild;
                
                if (newItemsContainer && newItemsContainer.children.length > 0) {
                    // Move each new image card into the existing gallery container
                    Array.from(newItemsContainer.children).forEach(item => {
                        galleryContainer.appendChild(item);
                    });
                    
                    // Update our offset for the next fetch
                    skip += limit;
                } else {
                    // No more images returned by the database
                    hasMore = false;
                    trigger.innerHTML = "<p>All images loaded.</p>";
                    trigger.style.color = "#444";
                }
            } catch (error) {
                console.error("Error loading more images:", error);
                trigger.innerHTML = "<p>Error loading more images.</p>";
            } finally {
                isLoading = false;
            }
        }
    }, {
        // Start fetching slightly before the user reaches the exact bottom (200px ahead of time)
        rootMargin: "200px" 
    });

    // Start observing the trigger div
    observer.observe(trigger);
}


// function initBulkSelection() {
//     const toggleBtn = document.getElementById('toggle-select-mode');
//     const galleryContainer = document.getElementById('main-gallery-container');
//     const bulkPanel = document.getElementById('bulk-actions-panel');
//     const selectedCountSpan = document.getElementById('selected-count');
//     const cancelBtn = document.getElementById('cancel-selection-btn');
//     const deleteBtn = document.getElementById('bulk-delete-btn');

//     if (!toggleBtn || !galleryContainer) return;

//     let isSelectMode = false;
//     let selectedImageIds = new Set(); // Using a Set prevents duplicates automatically

//     // 1. Toggle Select Mode
//     toggleBtn.addEventListener('click', () => {
//         isSelectMode = !isSelectMode;
        
//         if (isSelectMode) {
//             document.body.classList.add('select-mode');
//             toggleBtn.textContent = "Cancel Selection";
//             toggleBtn.style.background = "#6c757d";
//             toggleBtn.style.color = "white";
//         } else {
//             exitSelectMode();
//         }
//     });

//     // Cancel Button inside the panel
//     if (cancelBtn) {
//         cancelBtn.addEventListener('click', exitSelectMode);
//     }

//     // 2. Event Delegation for clicking images
//     // We attach the listener to the container so it works for infinitely scrolled images too
//     galleryContainer.addEventListener('click', (e) => {
//         if (!isSelectMode) return; // Do nothing if not in select mode
        
//         // Find the closest parent with class 'gallery-item'
//         const item = e.target.closest('.gallery-item');
//         if (!item) return;

//         // Prevent the link from navigating
//         e.preventDefault();

//         const imageId = parseInt(item.getAttribute('data-id'));
//         if (!imageId) return;

//         // Toggle selection state
//         if (selectedImageIds.has(imageId)) {
//             selectedImageIds.delete(imageId);
//             item.classList.remove('selected');
//         } else {
//             selectedImageIds.add(imageId);
//             item.classList.add('selected');
//         }

//         updatePanelUI();
//     });

//     // 3. Update the Panel Visibility and Count
//     function updatePanelUI() {
//         selectedCountSpan.textContent = selectedImageIds.size;
//         if (selectedImageIds.size > 0) {
//             bulkPanel.classList.add('visible');
//         } else {
//             bulkPanel.classList.remove('visible');
//         }
//     }

//     // 4. Exit Select Mode entirely
//     function exitSelectMode() {
//         isSelectMode = false;
//         document.body.classList.remove('select-mode');
//         toggleBtn.textContent = "Select Images";
//         toggleBtn.style.background = ""; // Reset to default
//         toggleBtn.style.color = "";
        
//         // Clear all selected visually
//         document.querySelectorAll('.gallery-item.selected').forEach(item => {
//             item.classList.remove('selected');
//         });
        
//         selectedImageIds.clear();
//         updatePanelUI();
//     }

//     // 5. Handle Bulk Delete
//     if (deleteBtn) {
//         deleteBtn.addEventListener('click', async () => {
//             const count = selectedImageIds.size;
//             if (count === 0) return;

//             // Confirm with user
//             const confirmed = confirm(`Are you sure you want to permanently delete ${count} image(s)? This cannot be undone.`);
//             if (!confirmed) return;

//             const idsArray = Array.from(selectedImageIds);

//             try {
//                 // Change button text while loading
//                 deleteBtn.textContent = "Deleting...";
//                 deleteBtn.disabled = true;

//                 const response = await fetch('/api/images/bulk-update', {
//                     method: 'POST',
//                     headers: {
//                         'Content-Type': 'application/json',
//                     },
//                     body: JSON.stringify({
//                         image_ids: idsArray,
//                         action: 'delete'
//                     })
//                 });

//                 if (!response.ok) {
//                     throw new Error(`Server returned ${response.status}`);
//                 }

//                 // Success! Remove the elements from the screen without reloading
//                 idsArray.forEach(id => {
//                     const el = document.querySelector(`.gallery-item[data-id="${id}"]`);
//                     if (el) {
//                         el.remove(); // Remove from DOM
//                     }
//                 });

//                 // Exit select mode
//                 exitSelectMode();

//             } catch (error) {
//                 console.error("Bulk delete failed:", error);
//                 alert("An error occurred while deleting images. Check the console.");
//             } finally {
//                 // Reset button
//                 deleteBtn.textContent = "Delete Selected";
//                 deleteBtn.disabled = false;
//             }
//         });
//     }
// }
