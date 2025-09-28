# Aetherium Gallery

A web-based application built with Python (FastAPI) to manage, visualize, and categorize AI-generated images, focusing on metadata and creative exploration.

# Project tree structure:

aetherium_gallery/
├── aetherium_gallery/
│ ├── routers/
│ │ ├── **init**.py
│ │ ├── frontend.py
│ │ └── images.py
│ ├── **init**.py
│ ├── config.py
│ ├── crud.py
│ ├── database.py
│ ├── main.py
│ ├── models.py
│ ├── schemas.py
│ └── utils.py
├── static/
│ ├── css/
│ │ └── style.css
│ └── js/
│ └── script.js
├── templates/
│ ├── base.html
│ ├── image.detail.html
│ ├── index.html
│ └── upload.html
├── uploads/
├── .env
├── .gitignore
├── README.md
└── requirements.txt

## Features (Initial Setup)

- **Image Upload:** Upload multiple images via a web form.
- **Gallery View:** Basic grid view displaying thumbnails.
- **Detail View:** View larger image and extracted/stored metadata.
- **Basic Metadata Extraction:** Attempts to parse dimensions and basic Stable Diffusion parameters from PNG info.
- **Thumbnail Generation:** Automatically creates thumbnails for faster gallery loading.
- **File Storage:** Stores images locally in an `uploads` directory.
- **Database:** Uses SQLAlchemy (async) with SQLite (default) to store image information.

## Setup and Running

1.  **Clone the Repository:**

    ```bash
    git clone <your-repository-url>
    cd aetherium-gallery
    ```

2.  **Create a Virtual Environment:**

    ```bash
    python -m venv venv
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment:**

    - Copy the `.env.example` file (if you create one) or create `.env` manually.
    - Ensure `DATABASE_URL` and `UPLOAD_FOLDER` are set correctly.
    - **Generate a `SECRET_KEY`**: Run `python -c 'import secrets; print(secrets.token_hex(32))'` and paste the output into `.env`.
    - Make sure the directory specified by `UPLOAD_FOLDER` (default: `uploads`) exists and the application has write permissions to it.

5.  **Run the Database Initialization (First Time):**
    The application attempts to create tables on startup (`init_db` in `database.py` called from `main.py`). Ensure this runs successfully the first time. For production or complex changes, use a migration tool like Alembic.

6.  **Run the Application (Development):**

    ```bash
    uvicorn aetherium_gallery.main:app --reload --host 0.0.0.0 --port 8000
    ```

    - `--reload`: Automatically restarts the server when code changes (for development).
    - `--host 0.0.0.0`: Makes the server accessible on your local network.
    - `--port 8000`: Specifies the port number.

7.  **Access the Application:**
    Open your web browser and navigate to `http://127.0.0.1:8000` or `http://<your-local-ip>:8000`.

## Next Steps & Planned Features

- Implement Tagging system (CRUD, assigning to images).
- Implement Albums/Collections.
- Robust Metadata Parsing (support for more formats, sidecar files).
- Advanced Search & Filtering (by metadata, tags).
- User Ratings & Favorites update via API.
- Batch Operations (tagging, deleting).
- Visual Similarity Search (using CLIP embeddings).
- "Evolution View" for comparing parameter changes.
- Smart Collections based on filters.
- User Authentication (optional).
- Background Task Processing (Celery) for intensive tasks (metadata extraction, embedding generation).
- Improved Frontend (HTMX or a JS framework).
- More sophisticated image editing/preview options.

## Contributing

[Details on how to contribute - if applicable]

## License

[Choose and specify a license, e.g., MIT]

Of course. Here are three "crazy" feature ideas that build upon your existing AI stack, pushing the boundaries from a gallery manager to a creative partner.

### 1. The "Dream Sequencer" — AI-Powered Storyteller

You are no longer just curating images; you are creating narrative journeys. This feature finds the conceptual "path" between two completely unrelated images in your gallery and uses an LLM to write a story about that journey.

*   **The Idea:** A user selects a "Start Image" (e.g., a photo of a calm beach) and an "End Image" (e.g., a rendering of a chaotic space battle). They then click "Dream Sequence."
*   **How it Works:**
    1.  **Vector Pathfinding:** The backend doesn't just find images similar to the start or end. It performs a "vector walk" through your gallery's entire DINOv2 index. It finds a chain of 5-7 images that represent the smoothest possible visual and conceptual transition from the beach, perhaps moving through a sunset, then a city at night, then clouds from an airplane, a satellite view of Earth, and finally arriving at the space battle.
    2.  **Narrative Generation:** This sequence of images, along with their existing descriptions and tags, is fed to a large language model like **Gemini 1.5 Pro**. The prompt is: "You are a surrealist author. Write a short, dream-like story that connects these sequential scenes. The story should flow from one image to the next."
*   **The Result:** The user is presented with a unique, scrollable story page that displays the sequence of images, each with a paragraph of a bizarre, AI-generated narrative that creates a cohesive, dream-like journey between their two chosen points. It turns your gallery into an engine for unexpected short stories.

### 2. The "Synesthetic Engine" — Generating Soundscapes for Images

The gallery is currently a silent experience. This feature adds a new sensory dimension by creating a unique, ambient "soundscape" for every image.

*   **The Idea:** On the `image_detail` page, next to the "Generate" icons for text, there is a new "Generate Soundscape" icon (e.g., 🎵).
*   **How it Works:**
    1.  **Prompt Synthesis:** When clicked, the backend gathers all the text associated with the image: the Gemini-generated description, the WD14 tags, and even the original prompt. It synthesizes this into a rich, descriptive prompt for a Text-to-Audio model. For an image of a neon-lit alley, the prompt might become: *"Sound of gentle rain on pavement, a distant futuristic police siren, the low electric hum of neon signs, muffled downtempo music coming from a doorway, a feeling of urban melancholy."*
    2.  **Audio Generation:** This synthesized prompt is sent to a dedicated Text-to-Audio AI model via an API. We would integrate a new library or service like **Stability AI's `stable-audio-tools`**, ElevenLabs (for sound effects), or a similar model designed for generating audio.
*   **The Result:** The API returns a 15-30 second audio file (MP3 or WAV). The frontend then displays a minimalist audio player under the image, allowing the user to play the unique ambient soundscape created specifically for that piece of art, making the viewing experience incredibly immersive.

### 3. The "Aesthetic Séance" — Chatting with the Ghost of Your Art Style

This is the most absurd idea. You don't just analyze an album's aesthetic; you summon its "ghost" and have a conversation with it.

*   **The Idea:** On an album page, there's a button labeled "Consult the Muse." Clicking it opens a chat window. You are not talking to a generic chatbot; you are talking to a persona dynamically created from the collective "soul" of the images in that album.
*   **How it Works:**
    1.  **Persona Synthesis:** When initiated, the backend analyzes the images in the album. It calculates the **average DINOv2 vector** (like in the "Creative Director" feature). But it also aggregates all the tags, descriptions, and metadata. It determines the most common themes (e.g., "cyberpunk, melancholy, neon"), the dominant color palette (using a library like **`colorgram.py`** to extract colors), and the overall complexity.
    2.  **Dynamic Meta-Prompting:** This synthesized persona is used to construct a detailed "meta-prompt" that is fed to **Gemini**. The prompt might be: *"You are the Muse of an art collection. Your personality is defined by these traits: [melancholy, futuristic, detailed]. Your visual world is made of [deep blues, electric pink]. Your primary subject is [portraits of androids]. You will now answer questions from a user from this specific point of view. Be creative and opinionated."*
    3.  **Interactive Chat:** A simple chat interface is created on the page using a library like **Gradio's `gr.ChatInterface`** (which can be embedded). Every time the user sends a message, it is appended to the ongoing conversation with the AI persona.
*   **The Result:** The user can have a conversation with the art itself. They could ask, "What is your purpose?" and the AI might respond, "To reflect on the loneliness of the digital age." Or "What should I create next?" and it might suggest ideas based on its core themes. It transforms a collection of images into an interactive creative entity.
