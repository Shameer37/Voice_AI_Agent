import torch, time
from sentence_transformers import SentenceTransformer

print("CUDA avail:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", device="cuda")
texts = ["hello world"]*2048
t0 = time.time(); _ = m.encode(texts, convert_to_numpy=True, batch_size=128, normalize_embeddings=True)
print("Encode secs:", round(time.time()-t0, 2))
