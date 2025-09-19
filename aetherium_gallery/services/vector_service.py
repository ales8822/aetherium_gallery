# aetherium_gallery/services/vector_service.py (FINAL STATELESS VERSION)

import faiss, numpy as np, pickle, os, logging
from transformers import AutoImageProcessor, AutoModel
import torch
from PIL import Image
from pathlib import Path

logger = logging.getLogger(__name__)

# This helper can be outside the class
def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec

class VectorService:
    def __init__(self, index_path: str = "./faiss_index.bin", mapping_path: str = "./faiss_mapping.pkl"):
        logger.info("Initializing Vector Service with FAISS and DINOv2...")
        self.model_name = "facebook/dinov2-base"
        self.embedding_dim = 768
        self.index_path = Path(index_path)
        self.mapping_path = Path(mapping_path)
        
        try:
            self.processor = AutoImageProcessor.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            logger.info("DINOv2 model and processor loaded successfully.")
        except Exception as e:
            raise
        
        # We ensure the files exist on startup, but we don't hold them in memory.
        self._load_or_create_index() 

    def generate_embedding(self, image_path: Path) -> np.ndarray | None:
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(images=image, return_tensors="pt")
            with torch.no_grad():
                outputs = self.model(**inputs)
            # Use the CLS token for a better global representation with DINOv2
            embedding = outputs.last_hidden_state[:, 0].squeeze().cpu().numpy()
            return _normalize_vector(embedding.astype("float32"))
        except: return None

    def add_image(self, image_id: int, image_path: Path):
        # Always load the latest index state from disk
        index, id_to_index, index_to_id = self._load_or_create_index()
        if image_id in id_to_index: return
        
        embedding = self.generate_embedding(image_path)
        if embedding is not None:
            index.add(np.array([embedding]))
            new_pos = index.ntotal - 1
            id_to_index[image_id] = new_pos
            index_to_id.append(image_id)
            # Save the updated index state back to disk immediately
            self._save_to_disk(index, id_to_index, index_to_id)
            logger.info(f"Successfully added and saved ID {image_id} to FAISS.")

    def find_similar_images_by_path(self, image_path: Path, source_id: int, n_results: int = 10) -> list[int]:
        SIMILARITY_THRESHOLD = 0.70
        query_embedding = self.generate_embedding(image_path)
        if query_embedding is None: return []

        # Always load the latest index state from disk
        index, _, index_to_id = self._load_or_create_index()
        if index.ntotal < 2: return []
        
        distances, indices = index.search(np.array([query_embedding]), n_results + 10) # Search more to filter
        
        similar_ids = []
        logger.info("--- Similarity Search Results ---")
        for i, dist in zip(indices[0], distances[0]):
            if i != -1 and i < len(index_to_id):
                retrieved_id = index_to_id[i]
                logger.info(f"Candidate ID: {retrieved_id}, Similarity Score: {dist:.4f}")
                if retrieved_id != source_id and dist >= SIMILARITY_THRESHOLD:
                    similar_ids.append(retrieved_id)
        
        final_ids = similar_ids[:n_results]
        logger.info(f"Final similar IDs passing threshold: {final_ids}")
        return final_ids

    def _save_to_disk(self, index, id_to_index, index_to_id):
        faiss.write_index(index, str(self.index_path))
        with open(self.mapping_path, 'wb') as f: pickle.dump({'id_to_index': id_to_index, 'index_to_id': index_to_id}, f)

    def _load_or_create_index(self) -> tuple:
        if self.index_path.exists() and self.mapping_path.exists():
            try:
                index = faiss.read_index(str(self.index_path))
                with open(self.mapping_path, 'rb') as f: mappings = pickle.load(f)
                return index, mappings['id_to_index'], mappings['index_to_id']
            except: pass
        
        index = faiss.IndexFlatIP(self.embedding_dim)
        return index, {}, []

# --- Singleton Instance ---
try:
    vector_service = VectorService()
except Exception as e:
    vector_service = None