# Basic trainer child class for text classification
# building on HuggingFace models
# Implemented by Forrest Davis 
# (https://github.com/forrestdavis)
# August 2024
from .Trainer import Trainer
import datasets
import transformers 
import sys

import numpy as np
import evaluate

# Load metrics
accuracy = evaluate.load("accuracy")
precision = evaluate.load('precision')
recall = evaluate.load('recall')
f1 = evaluate.load('f1')

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=-1)

    acc = accuracy.compute(predictions=predictions, references=labels)
    p = precision.compute(predictions=predictions, 
                                    references=labels,
                                    average='weighted', 
                                    zero_division=0)
    r = recall.compute(predictions=predictions, 
                                    references=labels,
                                    average='weighted', 
                                    zero_division=0)
    f = f1.compute(predictions=predictions, 
                                    references=labels,
                                    average='weighted')
    return {**acc, **p, **r, **f}

class HFTextClassificationTrainer(Trainer): 

    def __init__(self, config: dict, 
                **kwargs):
        super().__init__(config, **kwargs)

    def preprocess_function(self, examples):

        if self.pairLabel in examples:
            pairs = examples[self.pairLabel]
        else:
            pairs = None

        tokenized_inputs = self.Model.tokenizer(examples[self.textLabel],
                                    pairs, truncation=True)
        # Update labels if not ints
        labels = []
        for label in examples['label']:
            if not isinstance(label, int):
                if label not in self.Model.label2id:
                    sys.stderr.write(f"The labels must be ints. You can add "\
                                     "mappings via id2label in the config\n")
                labels.append(self.Model.label2id[label])
            else:
                labels.append(label)
        tokenized_inputs['label'] = labels

        return tokenized_inputs

    def preprocess_dataset(self):
        if self.dataset is None:
            self.set_dataset()

        if self.verbose:
            sys.stderr.write("Tokenizing the dataset...\n")
        self.dataset = self.dataset.map(self.preprocess_function, batched=True)
        self.data_collator = \
                    transformers.DataCollatorWithPadding(
                        tokenizer=self.Model.tokenizer._tokenizer)
    def train(self):

        if self.dataset is None:
            # Set up raw dataset
            self.set_dataset()

        if 'input_ids' not in self.dataset['train'].features:
            # Preprocess_dataset
            self.preprocess_dataset()

        # Shuffle
        self.dataset = self.dataset.shuffle(seed=42)

        use_cpu = False
        if str(self.Model.device) == 'cpu': 
            use_cpu = True

        training_args = transformers.TrainingArguments(
            output_dir=self.modelfpath,
            learning_rate=self.learning_rate,
            per_device_train_batch_size=self.batchSize,
            per_device_eval_batch_size=self.batchSize,
            num_train_epochs=self.epochs,
            weight_decay=self.weight_decay,
            eval_strategy=self.eval_strategy,
            eval_steps=self.eval_steps,
            save_strategy=self.save_strategy,
            save_steps=self.save_steps,
            load_best_model_at_end=self.load_best_model_at_end,
            use_cpu=use_cpu,
            )

        trainer = transformers.Trainer(
                model = self.Model.model, 
                args=training_args, 
                train_dataset=self.dataset['train'],
                eval_dataset=self.dataset['valid'],
                tokenizer=self.Model.tokenizer._tokenizer, 
                data_collator = self.data_collator, 
                compute_metrics = compute_metrics,
            )
        trainer.train()
        if self.verbose: 
            sys.stderr.write(f"Saving final model to {self.modelfpath}...\n")
        trainer.save_model()

