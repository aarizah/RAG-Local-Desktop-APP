from huggingface_hub import hf_hub_download
from dotenv import load_dotenv
import os

load_dotenv()

token = os.getenv("HuggingFaceToken")

model_path = hf_hub_download(
    repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
    filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    local_dir="./models",
    token=token
)

print("Hola")



print(f"Model downloaded to: {model_path}")