# Aetherium Gallery - Feature Roadmap

This document provides a comprehensive summary of all major features discussed for the Aetherium Gallery project. It is intended to be a living document for planning and tracking development progress.

---

## ✅ Core & Implemented Features

*These are the features that are complete and working in your application.*

*   `[DONE]` **Core Gallery Functionality**
    -   **Goal:** Provide the foundational features of a modern multimedia gallery.
    -   **How it Works:** Supports image and video uploads, a main gallery view with infinite scroll, tagging, and album organization. Includes a robust backend with FastAPI, SQLAlchemy, and a frontend with Jinja2 templates.
    -   **Notes:** This was the baseline from which we started.

*   `[DONE]` **AI-Powered Metadata Generation**
    -   **Goal:** Automatically enrich images with descriptive text and relevant tags using AI.
    -   **How it Works:** Uses Google Gemini for detailed descriptions and the WD14 Tagger for AI art-specific tags. This was refined to allow for selective (one-or-the-other) or combined ("Generate All") generation via inline icons on the image detail page.
    -   **Notes:** This feature has been fully implemented and refined for a better user experience.

*   `[DONE]` **Interactive On-Demand Generation at Upload**
    -   **Goal:** Allow the user to generate metadata, preview it, and approve it *before* the image is saved to the database.
    -   **How it Works:** A dedicated API endpoint (`/api/generation/generate-for-upload`) processes a temporary image file and returns the AI-generated text. The upload page UI was updated to call this endpoint, populate the form fields with the result, and let the user make final edits before submitting.
    -   **Notes:** This was a significant workflow improvement that gives the user full control.

*   `[DONE]` **Embedded Metadata Editor (Pillow Method)**
    -   **Goal:** Provide a way to read, edit, add, and remove custom metadata that is saved *directly into the image file itself*, creating a robust backup independent of the database.
    -   **How it Works:** Uses the Pillow library to read and write a single, dedicated JSON data chunk (`aetherium_gallery_data`) within the file's metadata. The UI presents this as a clean "User-Defined Data" section, separating it from read-only technical data and providing an excellent, reliable user experience.
    -   **Notes:** This feature replaced a complex and buggy ExifTool implementation with a far superior and more reliable pure-Python solution.

*   `[DONE]` **Bulk Upload System**
    -   **Goal:** Allow users to upload multiple files at once and apply a common set of metadata to the entire batch.
    -   **How it Works:** A completely overhauled, JavaScript-driven UI on the `/upload` page that manages a file queue. It uploads files one-by-one to an API endpoint and provides real-time progress for the batch and individual files.
    -   **Notes:** This significantly improves the efficiency of populating the gallery.

---

## 🚀 High Priority & In Progress

*These are the most logical and valuable next steps, building directly on the existing technology.*

*   `[IN PROGRESS]` **The Constellation Map**
    -   **Goal:** Create a stunning 2D "star map" visualization of the entire gallery, where each star is an image and clusters represent stylistically similar content.
    -   **How it Works:** Uses the `UMAP` library to perform dimensionality reduction on all DINOv2 vectors, converting them to 2D coordinates. These coordinates are stored in the database. A new page uses `Plotly.js` to render a high-performance, interactive scatter plot where users can explore, hover for previews, and click to navigate.
    -   **Notes:** All backend work for this feature (database changes, API calculation, data serving endpoint) is complete. The only remaining step is the frontend implementation on the `/map` page. **This is the highest priority.**

*   `[IMPORTANT]` **The "Creative Director" / Mood Board Analyzer**
    -   **Goal:** Analyze the "average aesthetic" of an entire album and recommend other images from the gallery that would be a perfect thematic fit.
    -   **How it Works:** Adds a button to the album detail page. The backend fetches the DINOv2 vectors for all images in the album, calculates their average vector, and uses this new "mood vector" to perform a global FAISS search, excluding images already in the album.
    -   **Notes:** This was the very first feature you requested. It's a natural and powerful extension of your vector search capabilities and should be a top priority after the Constellation Map.

*   `[IMPORTANT]` **"Chimeric Vision" — The Conceptual Blender**
    -   **Goal:** Allow a user to select 2 or more disparate images and find a single "conceptual average" or "Chimera" image from their gallery that best represents the blend of the selected concepts.
    -   **How it Works:** Similar to the Creative Director, but uses the bulk selection tool as input. It averages the vectors of the selected images and performs a global FAISS search.
    -   **Notes:** This is a fantastic "absurd" feature that is surprisingly easy to implement because all the required tools (vector averaging, FAISS search) have already been built. Highly recommended.

---

## 🧠 Must Think (Major Features / High Complexity)

*These ideas are incredibly powerful but would require significant new architectural pieces or dependencies.*

*   `[MUST THINK - Highly Complex]` **"The Eigengallery" — Distilling Your Personal Art Style into a New AI Model**
    -   **Goal:** Allow users to train their own mini-AI models (LoRAs) based on the curated style of an album.
    -   **How it Works:** Requires integrating a LoRA training pipeline (like `kohya_ss`), a GPU, and likely a cloud service API (like Replicate or Vast.ai) to handle the compute-intensive training process.
    -   **Notes:** The ultimate creative feedback loop, but a very large technical undertaking. A true "v2.0" feature.

*   `[MUST THINK - Architectural Change]` **The "Semantic Loom" — A Knowledge Graph of Your Art**
    -   **Goal:** Move beyond simple tags to an interconnected "brain" of concepts, allowing for complex queries like "show me knights *without* swords."
    -   **How it Works:** Requires heavy use of LLM Function Calling to extract structured data (`{subject, action, location}`) from descriptions and storing these relationships in a graph database like `Neo4j`.
    -   **Notes:** This would make your gallery an incredibly powerful asset management tool, but it involves adding a whole new type of database and changing the data ingestion flow.

*   `[MUST THINK - Highly Complex]` **"Chrono-Shuffle" — The Historical Art Style Time Machine**
    -   **Goal:** Re-imagine an image in the style of a historical art movement (e.g., as a medieval woodcut).
    -   **How it Works:** Requires adding a full image generation pipeline (e.g., Stable Diffusion) with ControlNet and IP-Adapter to transfer the style from a reference image while preserving the composition of the original.
    -   **Notes:** Like LoRA training, this is a massive feature that adds a full generation engine to your application.

---

## ✨ Cool Ideas & Fun Features (Lower Priority)

*These are creative, engaging features that add personality and new dimensions to the experience. They are excellent candidates for when the core utilities are complete.*

*   `[COOL IDEA]` **"World-Anvil" — Generative Story and World Bibles**
    -   **Goal:** Take a curated album and use a powerful LLM to generate a complete written "world bible" or story outline.
    -   **How it Works:** Gathers all images and metadata from an album and sends them to a large-custom LLM (like Gemini 1.5 Pro) with a master prompt instructing it to create factions, locations, characters, and plot hooks.
    -   **Notes:** An incredibly useful feature for creative users. It closes the loop between visual inspiration and structured narrative.

*   `[COOL IDEA]` **"Rhythm Weaver" — Automatic Music Video Director**
    -   **Goal:** Automatically create beat-synced, thematically relevant music videos from gallery images for an uploaded song.
    -   **How it Works:** Uses `librosa` for audio analysis (beat-mapping) and an LLM for lyric analysis to intelligently query and sequence images from the gallery.
    -   **Notes:** A very impressive, high-impact feature that adds an entirely new output medium to your application.

*   `[COOL IDEA]` **The "Synesthetic Engine" — Generating Soundscapes for Images**
    -   **Goal:** Create a unique, ambient soundscape for every image to make the viewing experience more immersive.
    -   **How it Works:** Synthesizes image metadata into a descriptive prompt for a Text-to-Audio model (like Stability AI's or ElevenLabs).
    -   **Notes:** A unique sensory feature that adds a lot of "wow" factor.

*   `[FUN IDEA - Low Utility]` **"The GAN-tagonist" — AI Critic and Art Roaster**
    -   **Goal:** Generate a humorous, scathing, or theatrical critique of an image from a cynical AI persona.
    -   **How it Works:** Uses a multi-modal LLM to analyze the image and prompt, combined with a persona-driven prompt to generate the "roast." Could be enhanced with text-to-voice.
    -   **Notes:** Purely for fun and engagement, but a very memorable feature.

*   `[USELESS - But Fun]` **"Aesthetic Séance" — Chatting with the Ghost of Your Art Style**
    -   **Goal:** Create a dynamic chatbot persona based on the collective aesthetic of an album, allowing the user to "talk to their art."
    -   **How it Works:** Combines vector averaging with LLM meta-prompting to create a unique personality for each album. Could use Gradio for the chat interface.
    -   **Notes:** Flagged as `Useless` from a purely practical "gallery management" perspective, but it is one of the most creatively interesting ideas. The definition of a "crazy" feature.