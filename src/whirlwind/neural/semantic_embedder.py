
import logging
from pathlib import Path

import open_clip
import torch
from huggingface_hub import hf_hub_download
from PIL import Image

from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.prompts.prompt_builders import PromptBank

class SemanticIntellect: 

    def __init__(self, spec: SCSpec) -> None:
        
        self.spec = spec
        self.device = torch.device(spec.device)
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
              spec.model_name
            ) 
        self.tokenizer = open_clip.get_tokenizer(spec.model_name)
        
        checkpoint_path = self._resolve_checkpoint()


        checkpoint = torch.load( 
                                checkpoint_path, 
                                map_location="cpu", 
                                weights_only=True)

        if isinstance(checkpoint, dict) and "state_dict" in checkpoint: 
              checkpoint = checkpoint["state_dict"]
        self.model.load_state_dict(checkpoint, strict=True) 
        self.model = self.model.to(self.device).eval()
    
    def _resolve_checkpoint(self) -> str: 
        if self.spec.checkpoint_path is not None: 
            path = Path(self.spec.checkpoint_path).expanduser()
            if not path.exists():
                raise FileNotFoundError("cannot find remoteclip checkpoint")
            return str(path)
        try:
            return hf_hub_download(
                repo_id=self.spec.hf_repo,
                filename=f"RemoteCLIP-{self.spec.model_name}.pt",
                cache_dir=str(Path(self.spec.cache_dir).expanduser()),
            )
        except RuntimeError as exc:
            if "client has been closed" in str(exc):
                raise RuntimeError(
                    "Hugging Face download failed because its HTTP client was closed. "
                    "Download the checkpoint manually and pass SCSpec(checkpoint_path=...). "
                    f"Expected filename: RemoteCLIP-{self.spec.model_name}.pt"
                ) from exc
            raise

    def encode_text_features(self, 
               bank: PromptBank
               ) -> torch.Tensor: 
        with torch.no_grad(): 
            text_tokens = self.tokenizer(list(bank.text_sets)).to(self.device)
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features
    
    def encode_image_features(self, image: Image.Image) -> torch.Tensor: 
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device) 
        with torch.no_grad(): 
            image_features = self.model.encode_image(image_tensor) 
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        return image_features
