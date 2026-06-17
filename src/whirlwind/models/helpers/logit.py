import torch 
from typing import Sequence, Mapping, Literal 
from whirlwind.prompts.prompt_builders import PromptBank



class PromptLogitator:
    """ handles raw model scores for semantic classification of 
        images with text prompts 

        used to represent logistical probability before 
        sigmoid, softmaxing, etc

    """
    
    def __init__(self, 
                 i_features: torch.Tensor, 
                 t_features: torch.Tensor, 
                 logit_scale: float, 
                 bank: PromptBank
                 ) -> None: 

        # image features 
        self.i_features = i_features 
        # text features 
        self.t_features = t_features

        self.logit_scale = logit_scale 
        self.bank = bank

    def _resolve_prompts(self) -> None:  
        self.prompt_logits =  (self.logit_scale * self.i_features @ self.t_features.T).squeeze(0)
    
    def _aggregate_by_class(
            self,
            *, 
            top_k: int, 
            ) -> torch.Tensor:  
        
        self._resolve_prompts()
        class_logits: list[torch.Tensor] = []
        for name in self.bank.classes: 
            indices = tuple(self.bank.prompt_indices_by_class[name]) 
            if not indices: 
                raise ValueError(f"class {name} has no prompts index oh no!")
            values = self.prompt_logits[list(indices)]
            k = min(max(int(top_k),1), int(values.numel()))
            class_logits.append(torch.topk(values, k=k).values.mean())
        return torch.stack(class_logits)

    def _softmax(self, logits: torch.Tensor) -> dict[str, float]:
        P = logits.softmax(dim=0).detach().cpu().numpy()
        return {
                class_name: float(p)
                for class_name, p in zip(self.bank.classes, P, strict=False)
                }

    def resolve_logits(self, top_k: int) -> torch.Tensor: 
        return self._aggregate_by_class(top_k=top_k)
    
    def resolve_scores(self, top_k: int,  method: Literal["softmax","sigmoid"]) -> dict[str, float]:
        if method == "softmax":
            logits = self.resolve_logits(top_k=top_k)
            return self._softmax(logits) 

        if method == "sigmoid":
            ...

        return {}
    


