# aetherium_gallery/services/vector_service.py (UPDATED with DEBBUGING)

import faiss, numpy as np, pickle, os, logging
from transformers import AutoImageProcessor, AutoModel
import torch
from PIL import Image
from pathlib import Path

logger = logging.getLogger(__name__)

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
            logger.error(f"Failed to load DINOv2 model: {e}")
            raise
        
        self._load_or_create_index() 

    def generate_embedding(self, image_path: Path) -> np.ndarray | None:
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(images=image, return_tensors="pt")
            with torch.no_grad():
                outputs = self.model(**inputs)
            embedding = outputs.last_hidden_state[:, 0].squeeze().cpu().numpy()
            return _normalize_vector(embedding.astype("float32"))
        except Exception as e:
            logger.error(f"Failed to generate embedding for {image_path}: {e}")
            return None

    def add_image(self, image_id: int, image_path: Path):
        index, id_to_index, index_to_id = self._load_or_create_index()
        if image_id in id_to_index: return
        
        embedding = self.generate_embedding(image_path)
        if embedding is not None:
            index.add(np.array([embedding]))
            new_pos = index.ntotal - 1
            id_to_index[image_id] = new_pos
            index_to_id.append(image_id)
            self._save_to_disk(index, id_to_index, index_to_id)
            logger.info(f"Successfully added and saved ID {image_id} to FAISS.")

    def find_similar_images_by_path(self, image_path: Path, source_id: int, n_results: int = 10) -> list[int]:
        SIMILARITY_THRESHOLD = 0.50
        query_embedding = self.generate_embedding(image_path)
        if query_embedding is None: return []

        return self.find_similar_images_by_vector(query_embedding, exclude_ids=[source_id], n_results=n_results, similarity_threshold=SIMILARITY_THRESHOLD)

    def get_embeddings_for_ids(self, image_ids: list[int]) -> np.ndarray | None:
        index, id_to_index, _ = self._load_or_create_index()
        if not image_ids or not id_to_index: return None
        
        embeddings = []
        for img_id in image_ids:
            faiss_index_pos = id_to_index.get(img_id)
            if faiss_index_pos is not None and faiss_index_pos < index.ntotal:
                embeddings.append(index.reconstruct(faiss_index_pos))
        
        return np.array(embeddings) if embeddings else None

    # ▼▼▼ UPDATED METHOD WITH DETAILED LOGGING ▼▼▼
    def find_similar_images_by_vector(self, query_vector: np.ndarray, exclude_ids: list[int], n_results: int = 24, similarity_threshold: float = 0.50) -> list[int]:
        index, _, index_to_id = self._load_or_create_index()
        if index.ntotal == 0: return []
        
        query_vector = query_vector.reshape(1, -1).astype('float32')
        
        k = n_results + len(exclude_ids) + 20 # Search for many results to ensure good candidates
        k = min(k, index.ntotal) # Don't search for more items than exist in the index
        distances, indices = index.search(query_vector, k=k)
        
        similar_ids = []
        
        # --- DEBUGGING LOGS ---
        logger.info(f"--- [Vector Search] Raw Similarity Scores (Threshold={similarity_threshold}) ---")
        for i, dist in zip(indices[0], distances[0]):
            if i != -1 and i < len(index_to_id):
                retrieved_id = index_to_id[i]
                
                # Check exclusion and threshold criteria
                is_excluded = retrieved_id in exclude_ids
                passes_threshold = dist >= similarity_threshold
                
                # Log every potential candidate and why it's included or not
                log_msg = f"Candidate ID: {retrieved_id}, Similarity: {dist:.4f} -> Excluded: {is_excluded}, Passes Threshold: {passes_threshold}"
                
                if not is_excluded and passes_threshold:
                    similar_ids.append(retrieved_id)
                    logger.info(log_msg + " [ADDED]")
                else:
                    logger.info(log_msg) # Still log it so we see the scores

        final_ids = similar_ids[:n_results]
        logger.info(f"--- [Vector Search] Final suggested IDs: {final_ids} ---")
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
            except Exception as e:
                logger.error(f"Error loading FAISS index or mappings: {e}. Recreating...")
        
        index = faiss.IndexFlatIP(self.embedding_dim)
        return index, {}, []

try:
    vector_service = VectorService()
except Exception as e:
    vector_service = None