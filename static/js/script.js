// Initially empty.
// You can add JavaScript here later for:
// - Client-side validation
// - Asynchronous operations (e.g., liking/favoriting without page reload)
// - Dynamic filtering/sorting
// - Interactive UI elements
// - Delete confirmations

console.log("Aetherium Gallery script loaded.");
// static/js/script.js

console.log("Aetherium Gallery script loaded.");

document.addEventListener("DOMContentLoaded", () => {
    // 1. Setup Infinite Scroll for the Gallery Index
    initInfiniteScroll();
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
// Example: Simple delete confirmation (though the HTML form has one too)
// document.addEventListener('DOMContentLoaded', () => {
//     const deleteButtons = document.querySelectorAll('.delete-button');
//     deleteButtons.forEach(button => {
//         button.addEventListener('click', (event) => {
//             if (!confirm('Are you sure you want to delete this image? This action cannot be undone.')) {
//                 event.preventDefault(); // Stop the form submission
//             }
//         });
//     });
// });
